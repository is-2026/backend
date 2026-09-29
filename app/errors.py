from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.models.error import Error


async def _validation_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    # loc es una tupla tipo ("body", "email"); el primer elemento es "body"
    campo = ".".join(str(p) for p in first["loc"][1:]) or "body"
    return JSONResponse(
        status_code=400,
        content=Error(message=f"{campo}: {first['msg']}").model_dump(),
    )


async def _http_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=Error(message=str(exc.detail)).model_dump(),
        headers=getattr(exc, "headers", None),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
