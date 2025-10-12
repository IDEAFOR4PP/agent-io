# =============================================================================
# Módulo de Herramientas de Producto (Versión con Sintaxis Asíncrona Correcta)
# =============================================================================

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select  # <--- Importación clave para la nueva sintaxis
from difflib import get_close_matches
import models

async def get_all_product_names(db: AsyncSession, business_id: int) -> list[str]:
    """Obtiene todos los nombres de productos para un negocio específico."""
    
    # --- CORRECCIÓN: Usar la sintaxis select() y await db.execute() ---
    stmt = select(models.Product.name).where(models.Product.business_id == business_id)
    result = await db.execute(stmt)
    # .scalars().all() extrae todos los resultados de la primera columna en una lista
    product_names = result.scalars().all()
    
    return [name.lower() for name in product_names]

async def buscar_producto(nombre_producto: str, business_id: int, db: AsyncSession) -> dict:
    """
    Busca un producto en la base de datos combinando búsqueda exacta y flexible.
    """
    # --- INICIO DE LA OPTIMIZACIÓN ---
    # Estrategia de búsqueda en dos pasos para máxima fiabilidad.

    # 1. Búsqueda con ILIKE: Potente para encontrar subcadenas.
    #    Ej: "jamon fud" encontrará "Jamón de Pavo Fud 250g".
    search_term = f"%{nombre_producto.replace(' ', '%')}%"
    stmt_ilike = select(models.Product).where(
        models.Product.business_id == business_id,
        models.Product.name.ilike(search_term)
    )
    result_ilike = await db.execute(stmt_ilike)
    producto = result_ilike.scalars().first()

    # 2. Búsqueda Fuzzy (si ILIKE falla): Buena para errores de tipeo.
    if not producto:
        product_names = await get_all_product_names(db, business_id=business_id)
        matches = get_close_matches(nombre_producto.lower(), product_names, n=1, cutoff=0.5)
        if matches:
            matched_name = matches[0]
            stmt_fuzzy = select(models.Product).where(
                models.Product.business_id == business_id,
                models.Product.name.ilike(matched_name)
            )
            result_fuzzy = await db.execute(stmt_fuzzy)
            producto = result_fuzzy.scalars().first()

    if not producto:
        return {"status": "error", "message": "Error interno al buscar el producto."}
    
    # --- INICIO DE LA CORRECCIÓN ---
    # Se reestructura la lógica para asegurar que el 'id' del producto
    # se incluya en 'product_details' en todos los casos donde el producto es encontrado.

    base_product_details = {
        "id": producto.id,
        "name": producto.name,
        "status": producto.availability_status,
        "unit": producto.unit
    }

    if producto.availability_status == 'CONFIRMED':
        if producto.price is None or producto.price <= 0:
            return {
                "status": "price_not_found",
                "message": f"Encontré el producto '{producto.name}', pero no tengo su precio en este momento.",
                "product_details": base_product_details
            }
        
        base_product_details["price"] = float(producto.price)
        return {
            "status": "success",
            "message": f"¡Sí tenemos {producto.name}! Cuesta ${producto.price:.2f}.",
            "product_details": base_product_details
        }
    
    elif producto.availability_status == 'OUT_OF_STOCK':
        return {
            "status": "out_of_stock",
            "message": f"Lo siento, por el momento se nos agotó el producto '{producto.name}'.",
            "product_details": base_product_details
        }
        
    elif producto.availability_status == 'UNCONFIRMED':
        return {
            "status": "unconfirmed",
            "message": f"Permíteme un momento para confirmar si tenemos '{producto.name}' y su precio.",
            "product_details": base_product_details
        }
        
    else: # REJECTED u otro estado
        return {
            "status": "not_available",
            "message": f"Lo siento, no manejamos el producto '{producto.name}'.",
        }