import httpx
import os
import logging

logger = logging.getLogger(__name__)

# --- INICIO DE LA MODIFICACIÓN ROBUSTA ---
# 1. Leemos las variables crudas del entorno.
raw_api_token = os.getenv("WHATSAPP_API_TOKEN")
raw_phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# 2. Saneamos las variables, eliminando espacios y comillas.
WHATSAPP_API_TOKEN = raw_api_token.strip().strip('"\'') if raw_api_token else None
WHATSAPP_PHONE_NUMBER_ID = raw_phone_id.strip().strip('"\'') if raw_phone_id else None
# --- FIN DE LA MODIFICACIÓN ROBUSTA ---

WHATSAPP_API_URL = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

async def send_whatsapp_message(to: str, message: str, api_token: str): # <-- AÑADE api_token
    """
    Envía un mensaje de texto a un número de WhatsApp usando un API Token específico.
    """
    # Lee el Phone Number ID de las variables de entorno (esto puede mejorar después)
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    
    # Valida que los datos necesarios están presentes
    if not api_token or not phone_number_id: # <-- VALIDA EL TOKEN RECIBIDO
        logger.error("Faltan el API Token o el Phone Number ID para enviar el mensaje.")
        return

    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {api_token}", # <-- USA EL TOKEN RECIBIDO
        "Content-Type": "application/json",
    }
    # Payload que cumple con la especificación de la API de Meta
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": message},
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(WHATSAPP_API_URL, json=payload, headers=headers)
            response.raise_for_status() # Lanza un error para respuestas 4xx o 5xx
            logger.info(f"Mensaje enviado exitosamente a {to}. Respuesta de Meta: {response.json()}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Error de API al enviar mensaje a {to}: {e.response.text}", exc_info=True)
        except Exception as e:
            logger.error(f"Error inesperado al enviar mensaje a {to}: {e}", exc_info=True)