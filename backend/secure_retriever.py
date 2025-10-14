# En backend/secure_retriever.py
import os
import asyncpg
import logging

logger = logging.getLogger(__name__)

# Clave para descifrar los tokens. NUNCA debe estar en el código.
ENCRYPTION_KEY = os.getenv("WHATSAPP_CREDENTIALS_SECRET_KEY")
# URL de la base de datos segura.
SECURE_DB_URL = os.getenv("SECURE_DATABASE_URL")

async def get_decrypted_api_token(business_phone_id: str) -> str | None:
    """
    Se conecta a la base de datos segura, busca un negocio por su phone_id
    y devuelve el API token descifrado.
    """
    if not all([ENCRYPTION_KEY, SECURE_DB_URL]):
        logger.error("Las variables de entorno para la base de datos segura no están configuradas.")
        return None

    conn = None
    try:
        conn = await asyncpg.connect(SECURE_DB_URL)
        # Llama a la función de PostgreSQL que creamos para descifrar.
        decrypted_token = await conn.fetchval(
            """
            SELECT get_decrypted_whatsapp_token(bw.business_id, $2)
            FROM secure_storage.business_whatsapp_credentials AS bw
            WHERE bw.whatsapp_phone_number_id = $1
            """,
            business_phone_id,
            ENCRYPTION_KEY
        )
        return decrypted_token
    except Exception as e:
        logger.error(f"No se pudo obtener el token descifrado para {business_phone_id}: {e}")
        return None
    finally:
        if conn:
            await conn.close()