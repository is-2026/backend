import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.behavior import BehaviorDB
from app.impl.behavior_api_impl import DetailBehaviorApiImpl


# Los parámetros llegan de abajo hacia arriba: BehaviorRepository, _get_club_id
@patch("app.impl.behavior_api_impl._get_club_id")
@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_get_behavior_return_behavior(
    mocked_repo_class,
    mocked_get_club_id,
):
    # TODO: quitar este mock cuando _get_club_id esté implementada
    club_id = uuid.uuid4()
    mocked_get_club_id.return_value = club_id

    behavior_id = uuid.uuid4()
    # BehaviorDB se puede instanciar sin base de datos, es solo un objeto
    behavior_db = BehaviorDB(
        id=behavior_id, 
        name="Correr", 
        code="def run(): pass", 
        club_id=club_id
    )

    mocked_repo = MagicMock()
    mocked_repo.get_id_and_club = AsyncMock(return_value=behavior_db)
    mocked_repo_class.return_value = mocked_repo

    # la sesión no se usa porque el repo está mockeado
    result = await DetailBehaviorApiImpl(MagicMock()).get_behavior(behavior_id)

    assert result.id == behavior_id
    assert result.name == "Correr"
    assert result.code == "def run(): pass"
    # la búsqueda tiene que filtrar por el club del usuario, si no, se filtra código ajeno
    mocked_repo.get_id_and_club.assert_awaited_once_with(
        behavior_id=behavior_id, club_id=club_id
    )

@patch("app.impl.behavior_api_impl._get_club_id")
@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_get_behavior_return_404(
    mocked_repo_class,
    mocked_get_club_id,
):
    # TODO: quitar este mock cuando _get_club_id esté implementada
    mocked_get_club_id.return_value = uuid.uuid4()

    # el repo devuelve None tanto si no existe como si es de otro club
    mocked_repo = MagicMock()
    mocked_repo.get_id_and_club = AsyncMock(return_value=None)
    mocked_repo_class.return_value = mocked_repo

    with pytest.raises(HTTPException) as exc_info:
        await DetailBehaviorApiImpl(MagicMock()).get_behavior(uuid.uuid4())

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "El comportamiento no existe"