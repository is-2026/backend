from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.apis.authentication_api_base import BaseAuthenticationApi
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.auth_response import AuthResponse
from app.models.user_register_input import UserRegisterInput
from app.repositories.user_repository import EmailExists, UserRepository
from app.security.passwords import hash_password
from app.security.tokens import create_access_token

PASSWORD_MIN_LENGTH = 5
PASSWORD_MAX_LENGTH = 64

_email_adapter = TypeAdapter(EmailStr)


def _normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    try:
        return _email_adapter.validate_python(email)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail="Email inválido") from e


def _validate_password(password: str) -> None:
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=(
                f"La contraseña debe tener entre {PASSWORD_MIN_LENGTH} y {PASSWORD_MAX_LENGTH} caracteres"
            ),
        )


class AutenticacionApiImpl(BaseAuthenticationApi):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register_user(
        self, user_register_input: UserRegisterInput
    ) -> AuthResponse:
        normalized_email = _normalize_email(user_register_input.email)
        password = user_register_input.password.get_secret_value()
        _validate_password(password)
        hashed = await hash_password(password)
        try:
            user = await UserRepository(self._session).create(normalized_email, hashed)
        except EmailExists as e:
            raise HTTPException(status_code=409, detail="Email ya registrado") from e
        return AuthResponse(token=create_access_token(user.id))
