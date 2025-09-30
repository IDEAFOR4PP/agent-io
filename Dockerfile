# Usa una imagen base oficial de Python.
# La versión 'slim' es más ligera, ideal para producción.
FROM python:3.11-slim

# Establece el directorio de trabajo dentro del contenedor.
WORKDIR /app

# Copia el archivo de dependencias primero.
# Docker guardará esta capa en caché si el archivo no cambia.
COPY requirements.txt .

# Instala las dependencias.
# --no-cache-dir reduce el tamaño de la imagen.
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de la aplicación al directorio de trabajo.
COPY . .

# Expone el puerto que la aplicación usará.
# Usamos 8080, que es un puerto común para servicios en la nube.
EXPOSE 8080

# El comando para ejecutar la aplicación cuando se inicie el contenedor.
# Usamos --host 0.0.0.0 para que sea accesible desde fuera del contenedor.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]