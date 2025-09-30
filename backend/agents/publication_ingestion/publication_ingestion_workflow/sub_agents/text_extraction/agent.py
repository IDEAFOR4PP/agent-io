from google.adk.agents import LlmAgent
from ... import config
from . import prompt

# Este agente recibe el texto del usuario, lo procesa y guarda
# el resultado en el estado de la sesión con la clave "text_extraction_result".
TextExtractionAgent = LlmAgent(
    name="TextExtractionAgent",
    description="Extrae entidades (nombre, precio, categoría) de un texto de producto.",
    model=config.GEMINI_MODEL,
    instruction=prompt.PROMPT,
    output_key="text_extraction_result"
)