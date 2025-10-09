# =============================================================================
# Módulo de Manejo de Agente (Versión con Nombres de Tools Corregidos)
# =============================================================================

import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

import models
from agents.prompt_generator import generate_prompt_for_business
from agents.tools.product_tools import buscar_producto as buscar_producto_impl
from agents.tools.cart_tools import (
    agregar_al_carrito as agregar_al_carrito_impl,
    ver_carrito as ver_carrito_impl,
    remover_del_carrito as remover_del_carrito_impl,      # <-- AÑADIR
    modificar_cantidad as modificar_cantidad_impl,        # <-- AÑADIR
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
    # 1. Definir los Wrappers con los nombres correctos que espera el LLM.
    
    async def buscar_producto(nombre_producto: str) -> dict: # <-- RENOMBRADO
        """Busca un producto por nombre en el inventario del negocio actual."""
        # --- INICIO DE LA MODIFICACIÓN ---
        # 1. Ejecutamos la búsqueda del producto como antes.
        search_result = await buscar_producto_impl(
            nombre_producto=nombre_producto, business_id=business.id, db=db
        )

        # 2. Interceptamos el estado 'unconfirmed' para el flujo Human-in-the-Loop.
        if search_result.get("status") == "unconfirmed":
            product_details = search_result.get("product_details", {})
            product_id = product_details.get("id")
            product_name = product_details.get("name")

            if product_id and product_name:
                # 3. Simulamos la notificación al dueño del negocio.
                #    En una implementación real, esto enviaría un WhatsApp, email, etc.
                logger.info(
                    f"[HUMAN-IN-THE-LOOP] Notificación para '{business.name}': "
                    f"El cliente '{customer_phone}' preguntó por el producto '{product_name}' (ID: {product_id}). "
                    f"Por favor, responde a través del sistema de gestión."
                )
        
        return search_result
        # --- FIN DE LA MODIFICACIÓN ---

    async def agregar_al_carrito(nombre_producto: str, cantidad: float) -> dict: # <-- RENOMBRADO
        """Agrega una cantidad específica de un producto al carrito de compras del cliente."""
        return await agregar_al_carrito_impl(
            nombre_producto=nombre_producto,
            cantidad=cantidad,
            db=db,
            business_id=business.id,
            customer_phone=customer_phone,
        )

    async def ver_carrito() -> dict: # <-- RENOMBRADO
        """Muestra el contenido actual del carrito de compras del cliente."""
        return await ver_carrito_impl(
            db=db, business_id=business.id, customer_phone=customer_phone
        )

    # 2. Generar el Prompt Dinámico (sin cambios)
    dynamic_instruction = generate_prompt_for_business(business)
    
    # 3. Instanciar el Agente, pasando las funciones con los nombres correctos.
    request_agent = Agent(
        name=f"agent_for_{business.id}",
        model="gemini-2.5-flash-lite",
        instruction=dynamic_instruction,
        tools=[
            buscar_producto,      # <-- ACTUALIZADO
            agregar_al_carrito,   # <-- ACTUALIZADO
            ver_carrito,          # <-- ACTUALIZADO
        ],
    )
    
    async def remover_del_carrito(nombre_producto: str) -> dict:
        """Elimina un producto por completo del carrito de compras del cliente."""
        return await remover_del_carrito_impl(
            nombre_producto=nombre_producto,
            business_id=business.id,
            customer_phone=customer_phone,
            db=db
        )

    async def modificar_cantidad(nombre_producto: str, nueva_cantidad: float) -> dict:
        """Modifica la cantidad de un producto en el carrito. Si la cantidad es 0, lo elimina."""
        return await modificar_cantidad_impl(
            nombre_producto=nombre_producto,
            nueva_cantidad=nueva_cantidad,
            business_id=business.id,
            customer_phone=customer_phone,
            db=db
        )
    # --- FIN DE NUEVOS WRAPPERS ---

    dynamic_instruction = generate_prompt_for_business(business)
    
    request_agent = Agent(
        name=f"agent_for_{business.id}",
        model="gemini-2.5-flash-lite",
        instruction=dynamic_instruction,
        tools=[
            buscar_producto,
            agregar_al_carrito,
            ver_carrito,
            remover_del_carrito,   # <-- AÑADIR A LA LISTA
            modificar_cantidad,    # <-- AÑADIR A LA LISTA
        ],
    )
  
    runner.agent = request_agent
    
    # ... (El resto del archivo no necesita cambios) ...

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