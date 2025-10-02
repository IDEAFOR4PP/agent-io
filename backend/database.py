# backend/database.py (Versión Corregida y Simplificada para Desarrollo Local)

import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from typing import AsyncGenerator

# --- Configuración ---
# Aquí definimos la URL de conexión para nuestro entorno local.
# La clave es usar "postgresql+asyncpg".
DATABASE_URL = "postgresql+asyncpg://postgres:8Skolie23$@localhost:5432/sales_agent_db"
logger = logging.getLogger(__name__)

# --- Inicialización de SQLAlchemy ---

try:
    # Creamos el motor asíncrono usando la URL correcta
    engine = create_async_engine(DATABASE_URL, echo=False) # echo=True para ver las queries SQL en la terminal

    # Creamos una fábrica de sesiones asíncronas
    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Base declarativa de la que heredarán nuestros modelos
    Base = declarative_base()

except Exception as e:
    logger.critical(f"No se pudo configurar el motor de la base de datos: {e}", exc_info=True)
    # Salimos si no podemos conectar, ya que la app no puede funcionar.
    raise

# --- Dependencia para FastAPI ---

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Generador de sesiones de base de datos que se inyectará en los endpoints.
    """
    async with AsyncSessionLocal() as session:
        yield session
