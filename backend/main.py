# main.py CORREGIDO

# 1. Importaciones de librerías de terceros
from fastapi import FastAPI, Request, Response, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List
import logging

# 2. Importaciones de nuestra aplicación (usando referencias relativas)
from . import models                             # <--- CORRECCIÓN 1: Importación unificada y relativa de 'models'
from .database import SessionLocal, engine        # <--- CORRECCIÓN 2: Importación relativa de 'database'

# --- Configuración Inicial ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crea las tablas en la base de datos (si no existen) al iniciar la app
models.Base.metadata.create_all(bind=engine)

# --- Definición de la App y Schemas ---
app = FastAPI(title="Sales Agent API")

class ProductSchema(BaseModel):
    id: int
    sku: str
    name: str
    price: float
    availability_status: str

    class Config:
        from_attributes = True

# --- Lógica de la Base de Datos ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Endpoints ---
@app.get("/")
def read_root():
    return {"status": "API is running"}

@app.get("/webhook")
def verify_webhook(request: Request):
    challenge = request.query_params.get("hub.challenge", "No challenge found")
    logger.info("Webhook verification challenge received.")
    return Response(content=challenge, media_type="text/plain")

@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.json()
    logger.info(f"Received webhook payload: {body}")
    return {"status": "received"}

@app.get("/products", response_model=List[ProductSchema])
def get_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Endpoint para listar todos los productos de la base de datos.
    """
    products = db.query(models.Product).offset(skip).limit(limit).all()
    return products