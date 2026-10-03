import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.models.auth_login_input import AuthLoginInput
from app.models.auth_response import AuthResponse

from app.impl.authentication_api_impl import AutenticacionApiImpl


@patch("app.impl.authentication_api_impl.create_access_token")
@patch("app.impl.authentication_api_impl.verify_password")
@patch("app.impl.authentication_api_impl.UserRepository")
async def test_login_success(
    mocked_repo_class, 
    mocked_verify_password, 
    mocked_create_token
):
    user_id = uuid.uuid4()
    login_input = AuthLoginInput(email="usuario@ejemplo.com", password="password123")

    # usuario mockeado que va a devolver la bd
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_user.hashed_password = "hashed_password_mock"
    mocked_repo = MagicMock()
    mocked_repo.get_by_email = AsyncMock(return_value=mock_user)
    mocked_repo_class.return_value = mocked_repo
    
    # salidas esperadas
    mocked_verify_password.return_value = True
    mocked_create_token.return_value = "token_falso_123"

   # login
    api = AutenticacionApiImpl(MagicMock())
    result = await api.login(login_input)

    # verifico
    assert isinstance(result, AuthResponse)
    assert result.token == "token_falso_123"
    
    # verificamos que se normalizo y busco el email correctamente
    mocked_repo.get_by_email.assert_awaited_once_with("usuario@ejemplo.com")
    # verificamos que se comparo la contraseña plana con el hash
    mocked_verify_password.assert_awaited_once_with("password123", "hashed_password_mock")


@patch("app.impl.authentication_api_impl.UserRepository")
async def test_login_returns_401_when_user_not_found(mocked_repo_class):
    login_input = AuthLoginInput(email="no_existe@ejemplo.com", password="password123")
    
    # repo mockeado que devuelve none 
    mocked_repo = MagicMock()
    mocked_repo.get_by_email = AsyncMock(return_value=None)
    mocked_repo_class.return_value = mocked_repo

    # login
    api = AutenticacionApiImpl(MagicMock())
    # excepcion 401
    with pytest.raises(HTTPException) as exc_info:
        await api.login(login_input)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Email o contraseña incorrectos"
    mocked_repo.get_by_email.assert_awaited_once_with("no_existe@ejemplo.com")


@patch("app.impl.authentication_api_impl.verify_password")
@patch("app.impl.authentication_api_impl.UserRepository")
async def test_login_returns_401_when_password_incorrect(
    mocked_repo_class, 
    mocked_verify_password
):
    login_input = AuthLoginInput(email="usuario@ejemplo.com", password="bad_password")
    
    # usuario mockeado
    mock_user = MagicMock()
    mock_user.hashed_password = "hashed_password_mock"
    mocked_repo = MagicMock()
    mocked_repo.get_by_email = AsyncMock(return_value=mock_user)
    mocked_repo_class.return_value = mocked_repo

    # forzamos la contraseña incorrecta
    mocked_verify_password.return_value = False

    # login
    api = AutenticacionApiImpl(MagicMock())
    # excepcion 401
    with pytest.raises(HTTPException) as exc_info:
        await api.login(login_input)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Email o contraseña incorrectos"
    mocked_verify_password.assert_awaited_once_with("bad_password", "hashed_password_mock")