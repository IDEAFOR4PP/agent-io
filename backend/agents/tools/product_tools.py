from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from difflib import get_close_matches
from ... import models

# La función de ayuda ahora también necesita el business_id
def get_all_product_names(db: Session, business_id: int) -> list[str]:
    products = db.query(models.Product.name).filter(models.Product.business_id == business_id).all()
    return [name[0].lower() for name in products]

# La tool principal ahora requiere el business_id
async def buscar_producto(nombre_producto: str, business_id: int, db: AsyncSession) -> dict: # <--- MARCAR COMO ASYNC
    """
    Busca un producto para un negocio específico usando búsqueda flexible (fuzzy matching)
    y responde según su estado de disponibilidad.
    """
    # 1. BÚSQUEDA FLEXIBLE (Ahora filtrada por negocio)
    product_names = get_all_product_names(db, business_id=business_id)
    matches = get_close_matches(nombre_producto.lower(), product_names, n=1, cutoff=0.7)

    if not matches:
        return {
            "status": "not_found",
            "message": f"Lo siento, no pude encontrar ningún producto parecido a '{nombre_producto}'.",
        }

    matched_name = matches[0]

    # 2. CONSULTA A LA BASE DE DATOS (Ahora con doble filtro)
    producto = db.query(models.Product).filter(
        models.Product.business_id == business_id, # <--- ¡FILTRO CLAVE!
        models.Product.name.ilike(matched_name)
    ).first()

    if not producto: # Doble verificación por si acaso
        return {"status": "error", "message": "Error interno al buscar el producto."}

    # 3. LÓGICA DE NEGOCIO BASADA EN 'availability_status' (Nuestro objetivo)
    if producto.availability_status == 'CONFIRMED':
        return {
            "status": "success",
            "message": f"¡Sí tenemos {producto.name}! Cuesta ${producto.price:.2f}.",
            "product_details": {
                "name": producto.name,
                "price": producto.price,
                "stock": producto.stock,
                "status": "CONFIRMED"
            }
        }
    elif producto.availability_status == 'OUT_OF_STOCK':
        return {
            "status": "out_of_stock",
            "message": f"Lo siento, por el momento se nos agotó el producto '{producto.name}'.",
            "product_details": {"name": producto.name, "status": "OUT_OF_STOCK"}
        }
    elif producto.availability_status == 'UNCONFIRMED':
        return {
            "status": "unconfirmed",
            "message": f"Permíteme un momento para confirmar si tenemos '{producto.name}' y su precio.",
            "product_details": {"name": producto.name, "status": "UNCONFIRMED"}
            # Aquí se dispararía la lógica del "Human-in-the-Loop"
        }
    else: # REJECTED u otro estado
        return {
            "status": "not_available",
            "message": f"Lo siento, no manejamos el producto '{producto.name}'.",
        }