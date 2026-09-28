## Cómo levantar el proyecto

Backend de FutBot: FastAPI y MySQL corriendo en Docker.

### Requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y **abierto** (no hace falta instalar Python ni MySQL localmente).
- Git.

### Pasos

1. Clonar el repositorio y entrar a la carpeta:
```bash
   SSH: git clone git@github.com:is-2026/backend.git
   HTTP: git clone https://github.com/is-2026/backend.git
```
```bash   
   cd backend/
```

2. Configurar las variables de entorno (`.env`):
   Copiá el archivo de ejemplo para crear tu configuración local:
```bash
   cp .env.example .env
```

3. Construir y levantar los contenedores (servidor y base de datos):
```bash
   docker compose up --build
```

4. Esperar a que la base de datos termine de inicializarse y la terminal muestre la verificación de inicio: `Conexión a MySQL OK` y luego `Application startup complete`. Abrir en el navegador:

   - **http://localhost:8000/docs**: documentación interactiva (Swagger) con todos los endpoints del contrato.
   - **http://localhost:8000**: debería responder con `200` y un mensaje `Backend funcionando`.

### Uso diario

| Acción | Comando |
|---|---|
| Levantar todo | `docker compose up` |
| Levantar en segundo plano | `docker compose up -d` |
| Reconstruir (si cambió el `Dockerfile` o `requirements.txt`) | `docker compose up --build` |
| Ver logs del backend | `docker compose logs -f backend` |
| Ver logs de la base de datos | `docker compose logs -f db` |
| Detener | `Ctrl+C` y luego `docker compose down` |

El servidor de FastAPI se recarga solo cuando editás archivos dentro de `app/`. Los datos de MySQL persisten automáticamente en un volumen de Docker llamado `db_data`.

### Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop no está abierto | Abrirlo y esperar a que termine de iniciar |
| `port is already allocated` | Otro programa usa el puerto 8000 o 3306 | Cerrarlo, o cambiar en `docker-compose.yaml` los puertos de la izquierda (ej: `"8001:8000"` o `"3307:3306"`) |
| `RuntimeError: Falta la variable de entorno...` | No copiaste el `.env.example` a `.env` | Ejecutar `cp .env.example .env` para crear el archivo |
| El backend no arranca y se queda esperando | La base de datos no está *healthy* | Revisar los logs con `docker compose logs db` para ver por qué falló la inicialización de MySQL |
