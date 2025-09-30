from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# Importa la Base declarativa de tus modelos
# Asumiremos que tu archivo de modelos se llama models.py
from models import Base 

# CADENA DE CONEXIÓN A TU BASE DE DATOS LOCAL
# Revisa que el usuario ('postgres'), la contraseña ('mysecretpassword'), 
# el host ('localhost'), el puerto ('5432') y el nombre de la base de datos ('sales_agent_db')
# sean correctos.
DATABASE_URL = "postgresql://postgres:mysecretpassword@localhost:5432/sales_agent_db"

# Crea el motor de la base de datos
engine = create_engine(DATABASE_URL)

# Crea una clase de sesión configurada
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_db_and_tables():
    """
    Función para crear la base de datos y todas las tablas definidas en los modelos.
    """
    # NOTA: En una aplicación real, no crearíamos la base de datos así, 
    # pero para empezar es suficiente. PostgreSQL necesita que la BD exista.
    # Primero necesitas crear la base de datos 'sales_agent_db' manualmente.
    print("Creando todas las tablas en la base de datos...")
    Base.metadata.create_all(bind=engine)
    print("Tablas creadas exitosamente.")

if __name__ == "__main__":
    # Esto permite ejecutar el script directamente para crear las tablas
    # Abre una herramienta de BD como DBeaver o psql y ejecuta: CREATE DATABASE sales_agent_db;
    # Luego, corre este script: python database.py
    create_db_and_tables()