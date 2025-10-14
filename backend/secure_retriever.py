# En backend/secure_retriever.py
import os
import asyncpg
import logging

logger = logging.getLogger(__name__)

# Clave para descifrar los tokens.
ENCRYPTION_KEY = os.getenv("WHATSAPP_CREDENTIALS_SECRET_KEY")
# URL de la base de datos segura (en formato SQLAlchemy).
SECURE_DB_URL_RAW = os.getenv("SECURE_DATABASE_URL")

async def get_decrypted_api_token(business_phone_id: str) -> str | None:
    """
    Se conecta a la base de datos segura, busca un negocio por su phone_id
    y devuelve el API token descifrado.
    """
    if not all([ENCRYPTION_KEY, SECURE_DB_URL_RAW]):
        logger.error("Las variables de entorno para la base de datos segura no están configuradas.")
        return None

    # --- INICIO DE LA SOLUCIÓN ROBUSTA ---
    # Traducimos la URL de formato SQLAlchemy ('postgresql+asyncpg://')
    # al formato que 'asyncpg' entiende directamente ('postgresql://').
    compatible_db_url = SECURE_DB_URL_RAW.replace("+asyncpg", "")
    # --- FIN DE LA SOLUCIÓN ROBUSTA ---

    conn = None
    try:
        # Usamos la URL compatible para la conexión.
        conn = await asyncpg.connect(compatible_db_url)
        
        decrypted_token = await conn.fetchval(
            """
            SELECT secure_storage.get_decrypted_whatsapp_token(bw.business_id, $2)
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