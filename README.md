## Cómo levantar el proyecto

Backend de FutBot: FastAPI corriendo en Docker.

### Requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y **abierto** (no hace falta instalar Python).
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

2. Construir y levantar el servidor:
```bash
   docker compose up --build
```

3. Esperar a que la terminal muestre `Application startup complete` y abrir en el navegador:

   - **http://localhost:8000/docs**: documentación interactiva (Swagger) con todos los endpoints del contrato.
   - **http://localhost:8000**: deberia responder con `200` y un mensaje `Backend funcionando`

### Uso diario

| Acción | Comando |
|---|---|
| Levantar | `docker compose up` |
| Levantar en segundo plano | `docker compose up -d` |
| Reconstruir (si cambió el `Dockerfile` o `requirements.txt`) | `docker compose up --build` |
| Ver logs | `docker compose logs -f backend` |
| Detener | `Ctrl+C` y luego `docker compose down` |

El servidor se recarga solo cuando editás archivos dentro de `app/`.

### Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop no está abierto | Abrirlo y esperar a que termine de iniciar |
| `port is already allocated` | Otro programa usa el puerto 8000 | Cerrarlo, o cambiar en `compose.yaml` `"8000:8000"` por `"8001:8000"` y entrar por `localhost:8001` |
