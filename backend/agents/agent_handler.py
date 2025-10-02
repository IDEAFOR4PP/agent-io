# =============================================================================
# Módulo de Manejo de Agente (Versión con Wrapper de Abstracción)
# =============================================================================

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .. import models
from .prompt_generator import generate_prompt_for_business
from .tools.product_tools import buscar_producto as buscar_producto_impl # Renombramos la implementación

logger = logging.getLogger(__name__)

# La función `ensure_session` es una buena práctica que podemos añadir aquí
async def ensure_session(
    session_service: InMemorySessionService, app_name: str, user_id: str, session_id: str
):
    existing = await session_service.list_sessions(app_name=app_name, user_id=user_id)
    if not any(s.id == session_id for s in existing.sessions):
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

async def process_customer_message(
    user_message: str,
    customer_phone: str,
    business: models.Business,
    db: AsyncSession,
    runner: Runner,
    session_service: InMemorySessionService
) -> str:
    """
    Orquesta la lógica de IA, usando un wrapper para abstraer
    las dependencias de la tool del LLM.
    """
    
    # --- 1. Definir el Wrapper de la Tool (La Capa de Abstracción) ---
    # Esta es la función que el LLM verá. Su firma solo contiene
    # tipos de datos simples que el LLM puede generar.
    async def buscar_producto_wrapper(nombre_producto: str) -> dict:
        """
        Busca un producto por nombre en el inventario del negocio actual.
        """
        # El wrapper llama a nuestra función de implementación real,
        # pasándole el contexto (db, business_id) que tiene disponible en este scope.
        return await buscar_producto_impl(
            nombre_producto=nombre_producto,
            business_id=business.id,
            db=db
        )

    # --- 2. Generar el Prompt Dinámico ---
    dynamic_instruction = generate_prompt_for_business(business)
    
    # --- 3. Instanciar el Agente para esta Petición ---
    request_agent = Agent(
        name=f"agent_for_{business.id}",
        model="gemini-2.5-flash-lite",
        instruction=dynamic_instruction,
        tools=[buscar_producto_wrapper], # Le pasamos el wrapper, no la implementación
    )
    
    runner.agent = request_agent
    
    # --- 4. Ejecutar el Agente a través del Runner ---
    session_id = f"{business.whatsapp_number}-{customer_phone}"
    app_name = "whsp_ai_sales_agent"

    await ensure_session(
        session_service=session_service, app_name=app_name, user_id=customer_phone, session_id=session_id
    )

    content = types.Content(role="user", parts=[types.Part(text=user_message)])
    final_response_text = "Lo siento, tuve un problema para procesar tu mensaje."

    try:
        events = runner.run_async(
            user_id=customer_phone, session_id=session_id, new_message=content
        )
        async for event in events:
            if event.is_final_response() and event.content and event.content.parts:
                final_response_text = event.content.parts[0].text
                break
    except Exception as e:
        logger.error(f"Error durante la ejecución del runner del ADK: {e}", exc_info=True)
        return "Hubo un inconveniente técnico, por favor intenta de nuevo más tarde."

    return final_response_text