import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.dependencies import get_current_club
from app.models.extra_models import TokenModel


@patch("app.dependencies.ClubRepository")
async def test_get_current_return_club_user(mocked_repo_class):
    user_id = uuid.uuid4()
    token = TokenModel(sub=str(user_id)) #paso  a formato str, porque JWT solo transporta texto

    club = MagicMock() #armo un club falso, con su repositorio
    mocked_repo = MagicMock()
    mocked_repo.get_by_user_id = AsyncMock(return_value=club)
    mocked_repo_class.return_value = mocked_repo  #conecto la clase falsa con el objeto

   
    session = MagicMock()
    result = await get_current_club(token=token, session=session)  #ejecuto la sesion falsa y mi funcion

    assert result is club
    
    mocked_repo.get_by_user_id.assert_awaited_once_with(user_id) #convierto de string a uuid para poder buscarlo


@patch("app.dependencies.ClubRepository")
async def test_get_current_club_devuelve_404_si_no_tiene_club(mocked_repo_class):
    token = TokenModel(sub=str(uuid.uuid4()))

    mocked_repo = MagicMock()
    mocked_repo.get_by_user_id = AsyncMock(return_value=None)
    mocked_repo_class.return_value = mocked_repo

    with pytest.raises(HTTPException) as exc_info:
        await get_current_club(token=token, session=MagicMock())

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "El usuario no tiene un club creado"