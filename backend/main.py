# =============================================================================
# Módulo Principal de la Aplicación WHSP-AI (Versión Final Integrada)
#
# Arquitectura:
# - FastAPI asíncrono con gestión de ciclo de vida 'lifespan'.
# - Inicialización de recursos globales (BD Engine, ADK Runner) al arranque.
# - Endpoint de webhook robusto que delega la lógica de IA a un manejador.
# =============================================================================

# --- 1. Importaciones ---
import logging
from contextlib import asynccontextmanager
from typing import List, AsyncGenerator, Any, Literal, Optional
import os 
import csv # <-- Importar para leer el inventario
import io 
#from dotenv import load_dotenv

import hmac
import hashlib
from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query, Header, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Importaciones de nuestro proyecto
import models
from database import engine, AsyncSessionLocal, Base as DatabaseBase
from agents.agent_handler import process_customer_message
from agents.sales_agent import root_agent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from whatsapp_client import send_whatsapp_message

WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")


# --- 2. Configuración Inicial ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CORRECCIÓN 2: Cargar el .env de forma explícita y robusta ---
# Construimos la ruta al archivo .env que está en el mismo directorio que main.py
#dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
#if os.path.exists(dotenv_path):
#    load_dotenv(dotenv_path=dotenv_path)
#    logger.info("Archivo .env cargado exitosamente.")
#else:
#    logger.warning("Archivo .env no encontrado. Asegúrate de que exista en la carpeta 'backend'.")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gestiona la inicialización y el cierre de recursos de la aplicación.
    Se ejecuta una sola vez al arrancar y una vez al apagar.
    """
    # --- FASE DE ARRANQUE ---
    logger.info("Iniciando servicios de la aplicación WHSP-AI...")

    # 1. Inicializa y verifica la conexión a la base de datos
    async with engine.begin() as conn:
        await conn.run_sync(DatabaseBase.metadata.create_all)
    logger.info("Motor de BD inicializado y tablas verificadas/creadas.")

    # 2. Inicializa el Runner del Agente de IA y sus servicios
    logger.info("Inicializando Runner del Agente de IA y sus servicios...")
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="whsp_ai_sales_agent",
        agent=root_agent,  # Se usa el agente base; se sobreescribirá en cada petición
        session_service=session_service,
    )
    
    # Almacenamos los recursos en el estado global y seguro de la app
    app.state.agent_runner = runner
    app.state.session_service = session_service
    logger.info("Runner del Agente de IA y servicios listos.")

    yield  # La aplicación está activa y lista para recibir peticiones

    # --- FASE DE APAGADO ---
    logger.info("Cerrando los servicios de la aplicación...")
    await engine.dispose()
    logger.info("Conexiones de la base de datos cerradas exitosamente.")

# --- 4. Inicialización de la Aplicación FastAPI ---
app = FastAPI(
    title="WHSP-AI Agent API",
    description="API para el agente de ventas conversacional multi-negocio.",
    version="1.0.0",
    lifespan=lifespan
)

# --- 5. Modelos de Datos Pydantic (Validación de Entradas/Salidas) ---

class WebhookPayload(BaseModel):
    business_phone: str
    customer_phone: str
    message: str

class ProductSchema(BaseModel):
    id: int
    sku: str
    name: str
    price: float
    availability_status: str

    class Config:
        from_attributes = True

class InventoryResponsePayload(BaseModel):
    product_id: int
    decision: Literal["SI", "NO"]
    price: Optional[float] = None

# --- 6. Inyección de Dependencias de la Base de Datos ---

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def process_inventory_file(inventory_content: str, business_id: int):
    """
    Tarea en segundo plano para leer el contenido de un CSV de inventario y poblar la base de datos.
    Formato esperado del CSV: sku,name,description,price
    """
    logger.info(f"Iniciando procesamiento de inventario para el negocio ID: {business_id}")
    
    async with AsyncSessionLocal() as db:
        try:
            # Usamos el contenido de texto directamente.
            stream = io.StringIO(inventory_content)
            reader = csv.reader(stream)

            next(reader, None) # Omitir cabecera

            products_to_add = []
            for row in reader:
                if len(row) >= 4:
                    sku, name, description, price = row[0], row[1], row[2], row[3]
                    new_product = models.Product(
                        sku=sku,
                        name=name,
                        description=description,
                        price=float(price),
                        business_id=business_id,
                        availability_status='CONFIRMED'
                    )
                    products_to_add.append(new_product)

            db.add_all(products_to_add)
            await db.commit()
            logger.info(f"Procesamiento de inventario completado. Se añadieron {len(products_to_add)} productos al negocio ID: {business_id}")

        except Exception as e:
            logger.error(f"Error procesando el contenido del inventario para el negocio ID {business_id}: {e}", exc_info=True)
            await db.rollback()


# --- 7. Endpoints de la API ---

@app.get("/")
async def read_root():
    """Endpoint de salud para verificar que la API está en línea."""
    return {"status": "WHSP-AI API is running"}


@app.post("/businesses")
async def create_business(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    business_type: str = Form(...),
    personality_description: str = Form(...),
    whatsapp_number: str = Form(...),
    inventory_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint para dar de alta un nuevo negocio y su inventario inicial.
    """
    # Verificamos si el negocio ya existe por su número de WhatsApp.
    result = await db.execute(
        select(models.Business).where(models.Business.whatsapp_number == whatsapp_number)
    )
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="Un negocio con este número de WhatsApp ya existe.")

    # 2. Leemos el contenido del archivo INMEDIATAMENTE y lo decodificamos.
    try:
        content_bytes = await inventory_file.read()
        inventory_content_str = content_bytes.decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el archivo de inventario: {e}")
    finally:
        await inventory_file.close()


    # Creamos el nuevo negocio
    new_business = models.Business(
        name=name,
        business_type=business_type,
        personality_description=personality_description,
        whatsapp_number=whatsapp_number
    )
    db.add(new_business)
    await db.commit()
    await db.refresh(new_business)

    # 3. Pasamos el CONTENIDO (string), no el objeto de archivo, a la tarea en segundo plano.
    background_tasks.add_task(process_inventory_file, inventory_content_str, new_business.id)
    
    logger.info(f"Negocio '{name}' creado con ID: {new_business.id}. El procesamiento de inventario se ha iniciado en segundo plano.")

    return {
        "status": "success",
        "message": "¡Negocio creado exitosamente! Tu inventario se está procesando y estará disponible en unos momentos.",
        "business_id": new_business.id
    }

# --- INICIO DE LA INTEGRACIÓN CON WHATSAPP ---

@app.api_route("/webhook", methods=["GET", "POST"])
async def handle_whatsapp_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Endpoint unificado para manejar la API de WhatsApp.
    - GET: Usado por Meta para verificar la URL del webhook.
    - POST: Usado para recibir notificaciones de mensajes de usuarios.
    """
    if request.method == "GET":
        # --- Lógica de Verificación del Webhook de Meta ---
        VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("Webhook verificado exitosamente por Meta.")
            # Meta espera que devolvamos el valor de 'challenge' como un entero.
            return int(challenge)
        else:
            logger.error("Falló la verificación del webhook de Meta. Tokens no coinciden.")
            raise HTTPException(status_code=403, detail="Error de verificación de token.")

    elif request.method == "POST":
        # --- Lógica de Procesamiento de Mensajes Entrantes ---
        payload = await request.json()
        logger.info(f"Payload de WhatsApp recibido: {payload}")

        try:
            # Extraemos los datos clave del complejo objeto JSON de Meta.
            change = payload['entry'][0]['changes'][0]
            if 'messages' not in change['value']:
                logger.info("Notificación de webhook recibida, pero no es un mensaje (ej. estado de entrega). Ignorando.")
                return {"status": "ignored_not_a_message"}

            message_object = change['value']['messages'][0]
            business_phone_id = change['value']['metadata']['phone_number_id'] # ID del número del negocio
            customer_phone = message_object['from'] # Número del cliente
            message_text = message_object['text']['body'] # Mensaje del cliente

            # Buscamos el negocio usando el ID del número de teléfono, que es más fiable.
            stmt = select(models.Business).where(models.Business.whatsapp_number_id == business_phone_id)
            result = await db.execute(stmt)
            business = result.scalars().first()
            
            if not business:
                logger.error(f"Negocio no encontrado para el ID de número de teléfono: {business_phone_id}")
                raise HTTPException(status_code=404, detail="Business not registered for this phone ID")

            # Delegamos la lógica de IA al agent_handler
            response_to_user = await process_customer_message(
                user_message=message_text,
                customer_phone=customer_phone,
                business=business,
                db=db,
                runner=app.state.agent_runner,
                session_service=app.state.session_service
            )

            # Enviamos la respuesta del agente de vuelta al usuario vía WhatsApp
            await send_whatsapp_message(to=customer_phone, message=response_to_user)
            
            logger.info(f"Respuesta del agente enviada a {customer_phone} vía WhatsApp.")
            # Respondemos a la API de Meta con un 200 OK para confirmar la recepción.
            return {"status": "processed_and_sent"}

        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"Payload de webhook recibido no tiene el formato de un mensaje estándar. Error: {e}. Ignorando.")
            return {"status": "ignored_malformed_payload"}
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            logger.critical(f"Error inesperado en el webhook de WhatsApp: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error interno del servidor.")

# --- FIN DE LA INTEGRACIÓN CON WHATSAPP ---
@app.post("/management/inventory_response")
async def handle_inventory_response(payload: InventoryResponsePayload, db: AsyncSession = Depends(get_db)):
    """
    Endpoint para que el dueño del negocio confirme o rechace un producto
    previamente marcado como 'unconfirmed'.
    """
    logger.info(f"Recibida respuesta de inventario para el producto ID: {payload.product_id}")

    # Buscamos el producto en la base de datos
    result = await db.execute(
        select(models.Product).where(models.Product.id == payload.product_id)
    )
    product = result.scalars().first()

    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    if payload.decision == "SI":
        if not payload.price or payload.price <= 0:
            raise HTTPException(status_code=400, detail="Se requiere un precio válido para confirmar el producto.")
        
        product.availability_status = "CONFIRMED"
        product.price = payload.price
        message = f"Producto '{product.name}' (ID: {product.id}) confirmado con precio ${payload.price}."
        
    elif payload.decision == "NO":
        product.availability_status = "REJECTED"
        message = f"Producto '{product.name}' (ID: {product.id}) ha sido rechazado."

    await db.commit()
    
    logger.info(message)
    return {"status": "success", "message": message}


@app.get("/products/{business_id}", response_model=List[ProductSchema])
async def get_business_products(business_id: int, skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Endpoint de utilidad para listar los productos de un negocio específico."""
    result = await db.execute(
        select(models.Product)
        .where(models.Product.business_id == business_id)
        .offset(skip).limit(limit)
    )
    products = result.scalars().all()
    return products
