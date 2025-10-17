# En backend/agents/agent_handler.py (añadir estas funciones y las importaciones necesarias)

import time
from typing import Optional, Dict, Any
from copy import deepcopy
from datetime import datetime

# Importaciones de ADK para Callbacks (asegúrate de que estén presentes)
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from google.adk.models import LlmResponse, LlmRequest
from google.adk.tools.base_tool import BaseTool
from google.genai import types # Asegúrate de importar types si no lo está

# Instancia del logger (ya deberías tenerla)
logger = logging.getLogger(__name__)

# --- Funciones de Callback ---

def log_callback_event(event_name: str, context: CallbackContext, details: Optional[Dict] = None):
    """Función de utilidad para loguear eventos de callback de forma estandarizada."""
    log_data = {
        "event": event_name,
        "agent": context.agent_name,
        "invocation_id": context.invocation_id,
        "session_id": context.session_id,
        "user_id": context.user_id,
    }
    if details:
        log_data.update(details)
    logger.info(log_data)

# -- Callbacks de Agente --
def before_agent_prod(callback_context: CallbackContext) -> Optional[types.Content]:
    """Se ejecuta ANTES de que el agente procese el mensaje."""
    callback_context.state['start_time'] = time.time() # Guardar tiempo de inicio en el estado
    log_callback_event("AgentStart", callback_context)
    return None # Continuar

def after_agent_prod(callback_context: CallbackContext) -> Optional[types.Content]:
    """Se ejecuta DESPUÉS de que el agente termina (respuesta final o error)."""
    start_time = callback_context.state.get('start_time', time.time())
    duration_ms = round((time.time() - start_time) * 1000, 2)
    log_callback_event("AgentEnd", callback_context, {"duration_ms": duration_ms})
    # Aquí podríamos añadir métricas a Prometheus/Datadog, etc.
    return None # Usar la respuesta generada

# -- Callbacks de Modelo (LLM) --
def before_model_prod(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    """Se ejecuta ANTES de llamar al LLM."""
    num_messages = len(llm_request.contents) if llm_request.contents else 0
    # Podríamos añadir validación de prompt aquí si fuera necesario (Patrón Guardián)
    log_callback_event("LlmRequest", callback_context, {"num_messages": num_messages})
    callback_context.state['llm_start_time'] = time.time()
    return None # Continuar

def after_model_prod(callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:
    """Se ejecuta DESPUÉS de recibir la respuesta del LLM."""
    llm_start_time = callback_context.state.get('llm_start_time', time.time())
    duration_ms = round((time.time() - llm_start_time) * 1000, 2)
    has_function_call = False
    response_text_preview = ""
    if llm_response.content and llm_response.content.parts:
        for part in llm_response.content.parts:
            if hasattr(part, 'function_call') and part.function_call:
                has_function_call = True
            if hasattr(part, 'text') and part.text:
                response_text_preview = part.text[:50] + "..." if len(part.text) > 50 else part.text

    log_callback_event("LlmResponse", callback_context, {
        "duration_ms": duration_ms,
        "has_function_call": has_function_call,
        "response_preview": response_text_preview
    })
    # Aquí podríamos añadir validación de respuesta (Patrón Guardián)
    return None # Usar la respuesta del LLM

# -- Callbacks de Herramientas --
def before_tool_prod(tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext) -> Optional[Dict]:
    """Se ejecuta ANTES de ejecutar una herramienta."""
    log_callback_event("ToolStart", tool_context, {"tool_name": tool.name, "args": args})
    tool_context.state['tool_start_time'] = time.time()

    # --- Inyección de Contexto Dinámico ---
    # Añadimos automáticamente los argumentos que nuestras tools necesitan
    # Esto elimina la necesidad de los wrappers dentro de process_customer_message
    if 'db' not in args:
        args['db'] = tool_context.state.get('db_session')
    if 'business_id' not in args:
        args['business_id'] = tool_context.state.get('business_id')
    if 'customer_phone' not in args:
        args['customer_phone'] = tool_context.user_id # user_id es el customer_phone

    # Validación básica de argumentos (ejemplo)
    if tool.name == "agregar_al_carrito" or tool.name == "modificar_cantidad":
        if not isinstance(args.get('cantidad'), (int, float)) or args.get('cantidad') < 0:
            logger.error(f"Argumento 'cantidad' inválido para {tool.name}: {args.get('cantidad')}")
            return {"status": "error", "message": "La cantidad proporcionada no es válida."} # Evita la ejecución

    return None # Permite la ejecución de la herramienta con los args (posiblemente modificados)

def after_tool_prod(tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext, tool_response: Dict) -> Optional[Dict]:
    """Se ejecuta DESPUÉS de ejecutar una herramienta."""
    tool_start_time = tool_context.state.get('tool_start_time', time.time())
    duration_ms = round((time.time() - tool_start_time) * 1000, 2)
    status = "success" if isinstance(tool_response, dict) and tool_response.get("status") in ["success", "empty"] else "error"

    log_callback_event("ToolEnd", tool_context, {
        "tool_name": tool.name,
        "status": status,
        "duration_ms": duration_ms,
        # "response": tool_response # Cuidado: Puede ser muy grande
    })
    # Podríamos modificar la respuesta aquí si fuera necesario
    return None # Usa la respuesta original de la herramienta

async def process_customer_message(
    user_message: str,
    customer_phone: str,
    business: models.Business,
    db: AsyncSession,
    runner: Runner,
    session_service: InMemorySessionService
    # Ya no necesitamos pasar memory_service aquí si lo integramos globalmente
) -> str:
    """
    Orquesta la lógica de IA usando Callbacks para monitorización y control.
    """
    app_name = "whsp_ai_sales_agent"
    session_id = f"{business.whatsapp_number}-{customer_phone}"

    # Asegura la sesión
    await ensure_session(
        session_service=session_service, app_name=app_name, user_id=customer_phone, session_id=session_id
    )

    # --- Lógica de Memoria (Si está integrada globalmente, se recupera aquí) ---
    # memory_service = # obtener de app.state si se movió a lifespan
    # search_results = await memory_service.search_memory(...)
    # final_instruction = ... (crear prompt con memoria recuperada)
    # Si no, generar prompt dinámico sin memoria por ahora:
    final_instruction = generate_prompt_for_business(business)

    # --- Estado Inicial para Callbacks ---
    # Pasamos datos necesarios a los callbacks a través del estado
    initial_state = {
        'db_session': db,
        'business_id': business.id,
        # 'customer_phone': customer_phone # user_id ya está en el contexto
    }
    # Cargamos el estado existente de la sesión si lo hubiera
    current_session_data = await session_service.get_session(app_name, customer_phone, session_id)
    if current_session_data and current_session_data.state:
         initial_state.update(current_session_data.state)


    # --- Instanciar el Agente con Callbacks ---
    # Pasamos las implementaciones directas de las tools
    request_agent = Agent(
        name=f"agent_for_{business.id}",
        model="gemini-2.5-flash-lite", # O el modelo configurado
        instruction=final_instruction,
        tools=[
            buscar_producto_impl,
            agregar_al_carrito_impl,
            ver_carrito_impl,
            remover_del_carrito_impl,
            modificar_cantidad_impl,
        ],
        # Registrar los callbacks de producción
        before_agent_callback=before_agent_prod,
        after_agent_callback=after_agent_prod,
        before_model_callback=before_model_prod,
        after_model_callback=after_model_prod,
        before_tool_callback=before_tool_prod,
        after_tool_callback=after_tool_prod,
    )

    runner.agent = request_agent

    # --- Ejecución del Agente ---
    content = types.Content(role="user", parts=[types.Part(text=user_message)])
    final_response_text = "Lo siento, tuve un problema para procesar tu mensaje." # Valor por defecto

    try:
        events = runner.run_async(
            user_id=customer_phone,
            session_id=session_id,
            new_message=content,
            initial_state=initial_state # <-- Pasamos el estado inicial
        )
        async for event in events:
            if event.is_final_response() and event.content and event.content.parts:
                final_response_text = event.content.parts[0].text
                break
    except Exception as e:
        logger.error(f"Error durante la ejecución del runner del ADK: {e}", exc_info=True)
        # Podríamos usar un callback de error aquí también
        return "Hubo un inconveniente técnico, por favor intenta de nuevo más tarde."

    # --- Guardado de Memoria (Si está integrada globalmente) ---
    # current_session = await session_service.get_session(...)
    # if current_session:
    #     await memory_service.add_session_to_memory(current_session)
    #     logger.info(...)

    return final_response_text