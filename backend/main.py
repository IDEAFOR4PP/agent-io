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
from typing import List, AsyncGenerator, Any
import os 
#from dotenv import load_dotenv

from fastapi import FastAPI, Request, Depends, HTTPException
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

# --- 6. Inyección de Dependencias de la Base de Datos ---

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# --- 7. Endpoints de la API ---

@app.get("/")
async def read_root():
    """Endpoint de salud para verificar que la API está en línea."""
    return {"status": "WHSP-AI API is running"}

@app.post("/webhook")
async def handle_webhook(payload: WebhookPayload, db: AsyncSession = Depends(get_db)):
    """
    Endpoint principal para recibir y procesar los mensajes de los clientes.
    """
    logger.info(f"Webhook recibido para el negocio: {payload.business_phone} de parte de: {payload.customer_phone}")
    try:
        # Etapa de Contextualización
        stmt = select(models.Business).where(models.Business.whatsapp_number == payload.business_phone)
        result = await db.execute(stmt)
        business = result.scalars().first()
        
        if not business:
            logger.error(f"Negocio no encontrado para el número: {payload.business_phone}")
            raise HTTPException(status_code=404, detail="Business not registered")

        # Etapa de Delegación a la Lógica de IA
        response_to_user = await process_customer_message(
            user_message=payload.message,
            customer_phone=payload.customer_phone,
            business=business,
            db=db,
            runner=app.state.agent_runner,
            session_service=app.state.session_service
        )
    except HTTPException as http_exc:
        # Re-lanzamos las excepciones HTTP para que FastAPI las maneje correctamente
        raise http_exc
    except Exception as e:
        logger.critical(f"Error inesperado en el endpoint /webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ocurrió un error interno en el servidor.")

    logger.info(f"Respondiendo al usuario: {response_to_user}")
    return {"status": "processed", "response_to_user": response_to_user}

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
