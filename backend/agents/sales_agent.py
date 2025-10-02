# =============================================================================
# Módulo del Agente Base (Plantilla)
#
# Define la configuración genérica y las herramientas disponibles
# para cualquier agente de ventas en el sistema.
# =============================================================================

from google.adk.agents import Agent
from .tools.product_tools import buscar_producto

# Este es nuestro agente 'plantilla'.
# Su propósito es inicializar el Runner en el lifespan con una configuración base.
# La instrucción real y las tools contextualizadas serán inyectadas en tiempo de ejecución.
root_agent = Agent(
    name="sales_agent_template",
    model="gemini-2.5-flash-lite",
    description="Agente de ventas base para la plataforma WHSP-AI.",
    
    # La instrucción puede ser genérica, ya que será sobreescrita.
    instruction="Eres un asistente de ventas.",
    
    # La lista de tools define TODAS las capacidades que el sistema puede tener.
    tools=[
        buscar_producto,
        # Aquí añadiremos futuras herramientas como 'agregar_al_carrito', etc.
    ],
)