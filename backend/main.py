# main.py
from fastapi import FastAPI, Request, Response
import logging

# Configura un logging básico para ver los mensajes en la terminal
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sales Agent API")

@app.get("/")
def read_root():
    return {"status": "API is running"}

# Este endpoint es para la verificación inicial que exige Meta
@app.get("/webhook")
def verify_webhook(request: Request):
    # Tu lógica de verificación irá aquí
    challenge = request.query_params.get("hub.challenge", "No challenge found")
    logger.info("Webhook verification challenge received.")
    return Response(content=challenge, media_type="text/plain")

@app.post("/webhook")
async def handle_webhook(request: Request):
    """
    Endpoint principal para recibir los mensajes de los clientes.
    """
    body = await request.json()
    logger.info(f"Received webhook payload: {body}")
    
    # FUTURO: Aquí es donde llamaremos a nuestro SalesWorkflowAgent
    
    return {"status": "received"}