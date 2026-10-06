import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.behavior import BehaviorDB
from app.impl.behavior_api_impl import BehaviorApiImpl


@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_list_behaviors_return_list(
    mocked_repo_class
):
    club_id = uuid.uuid4()
    
    # Creamos instancias mockeadas simulando lo que devuelve la BD
    behavior_1 = BehaviorDB(
        id=uuid.uuid4(), name="Correr", code="def run(): pass", club_id=club_id
    )
    behavior_2 = BehaviorDB(
        id=uuid.uuid4(), name="Saltar", code="def jump(): pass", club_id=club_id
    )

    # Configuramos el mock del repositorio para que devuelva la lista
    mocked_repo = MagicMock()
    mocked_repo.list_by_club = AsyncMock(return_value=[behavior_1, behavior_2])
    mocked_repo_class.return_value = mocked_repo

    # Instanciamos la API y llamamos al método con el club_id
    result = await BehaviorApiImpl(MagicMock()).list_behaviors(club_id)

    # Aserciones
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0].name == "Correr"
    assert result[1].name == "Saltar"
    
    # Verificamos que al repositorio le llegó el club_id correcto
    mocked_repo.list_by_club.assert_awaited_once_with(club_id)

@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_list_behaviors_return_empty(
    mocked_repo_class
):
    club_id = uuid.uuid4()

    # Configuramos el mock para que devuelva una lista vacía (sin resultados)
    mocked_repo = MagicMock()
    mocked_repo.list_by_club = AsyncMock(return_value=[])
    mocked_repo_class.return_value = mocked_repo

    result = await BehaviorApiImpl(MagicMock()).list_behaviors(club_id)

    # La aserción debe esperar exactamente una lista vacía
    assert result == []
    
    # Verificamos que la llamada al repositorio haya sido correcta
    mocked_repo.list_by_club.assert_awaited_once_with(club_id)

@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_get_behavior_return_behavior(
    mocked_repo_class
):
    club_id = uuid.uuid4()
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
    result = await BehaviorApiImpl(MagicMock()).get_behavior(behavior_id, club_id)

    assert result.id == behavior_id
    assert result.name == "Correr"
    assert result.code == "def run(): pass"
    # la búsqueda tiene que filtrar por el club del usuario, si no, se filtra código ajeno
    mocked_repo.get_id_and_club.assert_awaited_once_with(
        behavior_id=behavior_id, club_id=club_id
    )


@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_get_behavior_return_404(
    mocked_repo_class
):
    # el repo devuelve None tanto si no existe como si es de otro club
    mocked_repo = MagicMock()
    mocked_repo.get_id_and_club = AsyncMock(return_value=None)
    mocked_repo_class.return_value = mocked_repo

    with pytest.raises(HTTPException) as exc_info:  
        await BehaviorApiImpl(MagicMock()).get_behavior(uuid.uuid4(), uuid.uuid4())

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "El comportamiento no existe"