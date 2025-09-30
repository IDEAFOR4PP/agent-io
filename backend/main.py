import json
from contextlib import asynccontextmanager
from typing import Any
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, ValidationError

# --- Módulos del Proyecto ---
from backend import config
from backend.app import services, models
from backend import database
from backend.database import init_db_engine, close_db_engine, get_db
from backend.agents.publication_ingestion.publication_ingestion_workflow.agent import root_agent # Importamos el agente secuencial


from fastapi.middleware.cors import CORSMiddleware
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService


# --- Módulos de Google ADK y GenAI ---
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# --- Configuración Inicial ---
logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)
load_dotenv()

# --- Constantes de la Aplicación ---
APP_NAME = "tisales_ingestion_agent"
USER_ID = "ti_sales_user"
SESSION_ID = "ingestion_session_1"

async def ensure_session(
    session_service: InMemorySessionService,
    app_name: str,
    user_id: str,
    session_id: str,
    initial_state: dict[str, Any] | None = None,
) -> None:
    existing = await session_service.list_sessions(app_name=app_name, user_id=user_id)
    if not any(s.id == session_id for s in existing.sessions):
        await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            state=initial_state or {},
        )



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestiona el ciclo de vida completo de la aplicación:
    1. Inicializa y configura la conexión a la base de datos.
    2. Inicializa y configura el runner del agente de IA.
    3. Cierra los recursos de forma segura al apagar.
    """
    # --- FASE DE ARRANQUE (ANTES DE 'YIELD') ---
    
    # 1. Lógica de la Base de Datos
    logger.info("Inicializando motor de la base de datos...")
    db_connector = await init_db_engine()
    app.state.db_connector = db_connector  # Hacemos el conector accesible globalmente
    
    async with database.engine.begin() as conn:
        await conn.run_sync(database.Base.metadata.create_all)
    logger.info("Motor de BD inicializado y tablas verificadas/creadas.")

    # 2. Lógica del Agente de IA
    logger.info("Inicializando servicios del Agente de IA...")
    session_service = InMemorySessionService()
    await ensure_session(
        session_service,
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
        initial_state={"user_name": "Sky"},
    )
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    # Hacemos el runner y el servicio de sesión accesibles globalmente
    app.state.runner = runner
    app.state.session_service = session_service
    logger.info("Agente de IA y servicios listos.")

    try:
        yield  # La aplicación está lista para recibir peticiones
    finally:
        logger.info("Cerrando el conector de la base de datos...")
        await close_db_engine(db_connector)
        logger.info("Conector de la base de datos cerrado exitosamente.")


# Inicializa la aplicación con el gestor de ciclo de vida unificado
app = FastAPI(title="Culinary Agent API", lifespan=lifespan)


# --- Modelos Pydantic ---
class FormattedPublication(BaseModel):
    nombre: str
    descripcion_detallada: str
    precio: float
    categoria: str
    tags: list[str]

class PublicationResponse(BaseModel):
    message: str
    publication_id: int
    data: FormattedPublication

class AskBody(BaseModel):
    query: str

class TxTBody(BaseModel):
    text: str    

class ImageBody(BaseModel):
    image: UploadFile



# --- Endpoint Refactorizado ---

@app.post("/api/v1/publications", response_model=PublicationResponse)
async def create_publication_from_agent(
    product_text: str = Form(...),
    product_image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint de ingesta de productos.
    Recibe texto e imagen, los procesa con un agente secuencial de IA
    y persiste el resultado en la base de datos.
    """
    # --- Etapa 1: Ejecución del Agente Secuencial de IA ---
    try:
        runner: Runner = app.state.runner
        
        # El agente secuencial necesita tanto texto como imagen
        # Se construyen como 'parts' de un único mensaje de usuario
        content = types.Content(
            role="user",
            parts=[
                types.Part(text=product_text),
                types.Part(inline_data=types.Blob(
                    mime_type=product_image.content_type,
                    data=await product_image.read()
                ))
            ]
        )

        events = runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=content,
        )

        final_json_str = ""
        # Iteramos sobre los eventos y buscamos el que marca la respuesta final.
        async for event in events:
            if event.is_final_response() and event.content and event.content.parts:
                logger.info(f"Potential final response from [{event.author}]: {event.content.parts[0].text}")
                
                # --- INICIO DE LA CORRECCIÓN ---
                
                raw_text = event.content.parts[0].text
                
                # 1. Elimina espacios en blanco al inicio y al final.
                cleaned_text = raw_text.strip()
                
                # 2. Elimina los delimitadores de Markdown.
                # Usamos .removeprefix() y .removesuffix() que son más seguros que .replace().
                if cleaned_text.startswith("```json"):
                    cleaned_text = cleaned_text.removeprefix("```json")
                if cleaned_text.startswith("```"):
                    cleaned_text = cleaned_text.removeprefix("```")
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text.removesuffix("```")
                    
                # 3. Vuelve a limpiar espacios o saltos de línea que pudieran quedar.
                final_json_str = cleaned_text.strip()

        logger.info("Respuesta del Agente de IA...")
        if not final_json_str:
            raise HTTPException(status_code=502, detail="El flujo del agente de IA no generó una salida final.")

        agent_data = json.loads(final_json_str)
        validated_publication = FormattedPublication(**agent_data)

    except (ValidationError, json.JSONDecodeError) as e:
        logger.error(f"La respuesta del agente fue inválida. Error: {e}")
        raise HTTPException(status_code=502, detail=f"La respuesta del agente no pudo ser validada: {e}")
    except Exception as e:
        logger.critical(f"Error inesperado en el servicio de IA: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ocurrió un error con el servicio de IA.")

    # --- Etapa 2: Transacción Atómica con la Base de Datos ---
    try:
        categoria_nombre = validated_publication.categoria
        stmt = select(models.Categoria).where(models.Categoria.nombre == categoria_nombre)
        result = await db.execute(stmt)
        categoria_obj = result.scalars().first()
        
        if not categoria_obj:
            logger.info(f"Categoría '{categoria_nombre}' no encontrada. Creando nueva.")
            categoria_obj = models.Categoria(
                nombre=categoria_nombre, 
                descripcion=f"Categoría para {categoria_nombre}"
            )
            db.add(categoria_obj)
            await db.flush()

        vendedor_fijo_id = 1 # En un futuro, este ID vendrá del token de autenticación del vendedor
        
        nueva_publicacion = models.ProductoServicio(
            vendedor_id=vendedor_fijo_id,
            categoria_id=categoria_obj.id,
            nombre=validated_publication.nombre,
            descripcion_detallada=validated_publication.descripcion_detallada,
            precio=validated_publication.precio,
            tags=validated_publication.tags
        )
        
        db.add(nueva_publicacion)
        await db.commit()
        await db.refresh(nueva_publicacion)
        
        logger.info(f"Publicación '{nueva_publicacion.nombre}' guardada en BD. ID: {nueva_publicacion.id}")

        return PublicationResponse(
            message="Publicación creada y guardada con éxito.",
            publication_id=nueva_publicacion.id,
            data=validated_publication
        )
    except Exception as e:
        await db.rollback()
        logger.critical(f"Error en la transacción de la base de datos: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al guardar la publicación en la base de datos.")
