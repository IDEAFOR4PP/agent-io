# backend/whatsapp_client.py

import httpx
import os
import logging

logger = logging.getLogger(__name__)

# --- Carga de Configuración ---
# Leemos las credenciales desde las variables de entorno.
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_API_URL = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

async def send_whatsapp_message(to: str, message: str):
    """
    Envía un mensaje de texto a un usuario a través de la API de WhatsApp Business.
    """
    if not all([WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID]):
        logger.error("Faltan variables de entorno de WhatsApp. No se puede enviar el mensaje.")
        return

    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
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