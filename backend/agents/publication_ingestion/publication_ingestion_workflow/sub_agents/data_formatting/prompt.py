PROMPT = """
Eres un especialista en limpieza y formato de datos. Tu única tarea es combinar la información de los pasos anteriores en un único JSON final y limpio.

**Datos de Análisis de Imagen:**
```json
{image_analysis_result}
```

**Datos de Extracción de Texto:**
```json
{text_extraction_result}
```

Sigue estas instrucciones estrictamente:
1.  Extrae la "descripcion_imagen" del primer JSON y asígnala a una nueva clave "descripcion_detallada".
2.  Extrae los "tags" del primer JSON.
3.  Extrae "nombre", "precio", y "categoria" del segundo JSON.
4.  Combina todos estos datos en un solo objeto JSON.
5.  Asegúrate de que el campo 'precio' sea un número flotante (float).
6.  El JSON final debe contener exactamente estas claves: "nombre", "descripcion_detallada", "precio", "categoria", "tags".
"""