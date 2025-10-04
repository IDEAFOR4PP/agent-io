# =============================================================================
# Módulo de Manejo de Agente (Versión con Tools de Carrito Integradas)
#
# Orquesta la ejecución del agente, incluyendo las nuevas capacidades
# transaccionales para la gestión del carrito de compras.
# =============================================================================

import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .. import models
from .prompt_generator import generate_prompt_for_business
# Importamos las implementaciones de las tools con alias para mayor claridad
from .tools.product_tools import buscar_producto as buscar_producto_impl
from .tools.cart_tools import (
    agregar_al_carrito as agregar_al_carrito_impl,
    ver_carrito as ver_carrito_impl,
)

logger = logging.getLogger(__name__)

async def ensure_session(
    session_service: InMemorySessionService, app_name: str, user_id: str, session_id: str
):
    """Asegura que una sesión de conversación exista antes de ser utilizada."""
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
    Orquesta la lógica de IA, usando wrappers para abstraer
    las dependencias de las tools del LLM.
    """
    
    # --- 1. Definir los Wrappers de las Tools (Capas de Abstracción) ---
    
    # Wrapper para la búsqueda de productos (existente)
    async def buscar_producto_wrapper(nombre_producto: str) -> dict:
        """Busca un producto por nombre en el inventario del negocio actual."""
        return await buscar_producto_impl(
            nombre_producto=nombre_producto, business_id=business.id, db=db
        )

    # --- NUEVO: Wrapper para agregar productos al carrito ---
    async def agregar_al_carrito_wrapper(nombre_producto: str, cantidad: float) -> dict:
        """Agrega una cantidad específica de un producto al carrito de compras del cliente."""
        return await agregar_al_carrito_impl(
            nombre_producto=nombre_producto,
            cantidad=cantidad,
            db=db,
            business_id=business.id,
            customer_phone=customer_phone,
        )

    # --- NUEVO: Wrapper para ver el carrito ---
    async def ver_carrito_wrapper() -> dict:
        """Muestra el contenido actual del carrito de compras del cliente."""
        return await ver_carrito_impl(
            db=db, business_id=business.id, customer_phone=customer_phone
        )

    # --- 2. Generar el Prompt Dinámico ---
    dynamic_instruction = generate_prompt_for_business(business)
    
    # --- 3. Instanciar el Agente para esta Petición ---
    # Ahora incluimos las nuevas herramientas en la lista que el agente conoce.
    request_agent = Agent(
        name=f"agent_for_{business.id}",
        model="gemini-2.5-flash-lite",
        instruction=dynamic_instruction,
        tools=[
            buscar_producto_wrapper,
            agregar_al_carrito_wrapper,
            ver_carrito_wrapper,
        ],
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