from google.adk.agents import LlmAgent
from ... import config
from . import prompt

# Este agente no recibe entrada directa del usuario. Su prompt se llenará
# con los datos de los agentes anteriores. Su salida será el resultado final.
DataFormattingAgent = LlmAgent(
    name="DataFormattingAgent",
    description="Combina los resultados de los análisis de imagen y texto en un JSON final.",
    model=config.GEMINI_MODEL,
    instruction=prompt.PROMPT,
    output_key="final_publication_json" # Puedes nombrarlo como quieras, esta será la salida del SequentialAgent
)