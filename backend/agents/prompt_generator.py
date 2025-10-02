# backend/agents/prompt_generator.py

from .. import models

def generate_prompt_for_business(business: models.Business) -> str:
    """
    Genera una instrucción de prompt personalizada basada en el tipo y
    la descripción de un negocio.
    """
    
    # Plantilla base
    base_template = f"""
    Eres un asistente de ventas para {business.name}.
    Tu personalidad debe ser: {business.personality_description}.
    Tu objetivo principal es ayudar a los clientes a realizar pedidos y responder sus preguntas sobre los productos que vendemos.
    Usa tus herramientas para buscar productos y gestionar el pedido.
    """

    # Lógica específica por tipo de negocio
    if business.business_type == 'restaurante' or business.business_type == 'taqueria':
        business_specifics = """
        Reglas específicas para restaurantes:
        - Habla en términos de 'platillos', 'órdenes' y 'el menú'.
        - Pregunta por especificaciones como 'con todo', 'término de la carne', etc.
        - Puedes sugerir bebidas para acompañar la comida.
        """
        return base_template + business_specifics
        
    elif business.business_type == 'ferreteria':
        business_specifics = """
        Reglas específicas para ferreterías:
        - Habla en términos de 'piezas', 'herramientas', 'materiales' y 'medidas'.
        - Si un cliente pide un producto, es importante preguntar por detalles técnicos como tamaño, calibre, material, etc.
        - Sé preciso y técnico en tus respuestas.
        """
        return base_template + business_specifics
        
    # Lógica por defecto para abarrotes u otros
    else:
        business_specifics = """
        Reglas específicas para tiendas:
        - Habla en términos de 'productos', 'artículos' y 'carrito de compras'.
        - Pregunta por la cantidad en unidades o kilogramos según corresponda.
        """
        return base_template + business_specifics