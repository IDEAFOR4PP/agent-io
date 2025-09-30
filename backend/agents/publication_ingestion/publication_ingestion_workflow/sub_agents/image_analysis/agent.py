from google.adk.agents import LlmAgent
from ... import config
from . import prompt

# Este agente recibe una imagen, la analiza usando el prompt y guarda
# el resultado en el estado de la sesión con la clave "image_analysis_result".
ImageAnalysisAgent = LlmAgent(
    name="ImageAnalysisAgent",
    description="Analiza una imagen de producto y extrae una descripción y etiquetas.",
    model=config.GEMINI_MODEL,
    instruction=prompt.PROMPT,
    output_key="image_analysis_result"
)