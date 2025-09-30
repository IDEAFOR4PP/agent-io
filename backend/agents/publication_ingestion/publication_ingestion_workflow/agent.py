from google.adk.agents import SequentialAgent
from .sub_agents.image_analysis.agent import ImageAnalysisAgent
from .sub_agents.text_extraction.agent import TextExtractionAgent
from .sub_agents.data_formatting.agent import DataFormattingAgent

# Creamos el orquestador como antes
pipeline_agent = SequentialAgent(
    name="PublicationIngestionWorkflow",
    description="Ejecuta un flujo de 3 pasos para procesar una nueva publicación de producto.",
    sub_agents=[
        ImageAnalysisAgent,
        TextExtractionAgent,
        DataFormattingAgent
    ]
)

# Para máxima compatibilidad con las herramientas del ADK,
# se exporta el agente raíz con el nombre 'root_agent'.
root_agent = pipeline_agent


