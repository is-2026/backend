import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.behavior import BehaviorDB
from app.engine.behavior_exec import InvalidBehaviorCode
from app.engine.validation import validate_behavior_code
from app.impl.behavior_api_impl import BehaviorApiImpl
from app.models.create_behavior_input import CreateBehaviorInput, UpdateBehaviorInput
from app.repositories.behavior_repository import DuplicateNameBehavior


@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_list_behaviors_return_list(mocked_repo_class):
    club_id = uuid.uuid4()

    # Creamos instancias mockeadas simulando lo que devuelve la BD
    behavior_1 = BehaviorDB(
        id=uuid.uuid4(),
        name="Correr",
        code="def decide_action():\n    pass",
        club_id=club_id,
    )
    behavior_2 = BehaviorDB(
        id=uuid.uuid4(),
        name="Saltar",
        code="ddef decide_action():\n    pass",
        club_id=club_id,
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
async def test_list_behaviors_return_empty(mocked_repo_class):
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
async def test_get_behavior_return_behavior(mocked_repo_class):
    club_id = uuid.uuid4()
    behavior_id = uuid.uuid4()
    # BehaviorDB se puede instanciar sin base de datos, es solo un objeto
    behavior_db = BehaviorDB(
        id=behavior_id,
        name="Correr",
        code="def decide_action():\n    pass",
        club_id=club_id,
        kind="player",
    )

    mocked_repo = MagicMock()
    mocked_repo.get_id_and_club = AsyncMock(return_value=behavior_db)
    mocked_repo_class.return_value = mocked_repo

    # la sesión no se usa porque el repo está mockeado
    result = await BehaviorApiImpl(MagicMock()).get_behavior(behavior_id, club_id)

    assert result.id == behavior_id
    assert result.name == "Correr"
    assert result.code == "def decide_action():\n    pass"
    assert result.kind == "player"
    # la búsqueda tiene que filtrar por el club del usuario, si no, se filtra código ajeno
    mocked_repo.get_id_and_club.assert_awaited_once_with(
        behavior_id=behavior_id, club_id=club_id
    )


@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_get_behavior_return_404(mocked_repo_class):
    # el repo devuelve None tanto si no existe como si es de otro club
    mocked_repo = MagicMock()
    mocked_repo.get_id_and_club = AsyncMock(return_value=None)
    mocked_repo_class.return_value = mocked_repo

    with pytest.raises(HTTPException) as exc_info:
        await BehaviorApiImpl(MagicMock()).get_behavior(uuid.uuid4(), uuid.uuid4())

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "El comportamiento no existe"


@patch("app.impl.behavior_api_impl.validate_behavior_code")
@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_create_behavior_succes(mocked_repo_class, mocked_validate):
    club_id = uuid.uuid4()
    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id=behavior_id,
        name="CorrerCorrerCorrerCorrerCorrer",
        code="def decide_action():\n    pass",
        club_id=club_id,
        kind="player",
    )
    mocked_repo = MagicMock()
    mocked_repo.create = AsyncMock(return_value=behavior_db)
    mocked_repo_class.return_value = mocked_repo

    data = CreateBehaviorInput(
        name="CorrerCorrerCorrerCorrerCorrer",
        code="def decide_action():\n    pass",
        kind="player",
    )
    result = await BehaviorApiImpl(MagicMock()).create_behavior(data, club_id)

    assert result.id == behavior_id
    assert result.name == "CorrerCorrerCorrerCorrerCorrer"
    assert result.code == "def decide_action():\n    pass"
    assert result.kind == "player"

    mocked_validate.assert_called_once_with(
        "def decide_action():\n    pass", "player"
    )  # verifico que valido con el codigo y con el kind correctos
    mocked_repo.create.assert_awaited_once_with(
        club_id,
        "CorrerCorrerCorrerCorrerCorrer",
        "def decide_action():\n    pass",
        "player",
    )


@pytest.mark.parametrize("name", ["", "   ", "\n"])
@patch("app.impl.behavior_api_impl.validate_behavior_code")
@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_create_behavior_name_empty(mocked_repo_class, mocked_validate, name):
    club_id = uuid.uuid4()
    mocked_repo = MagicMock()
    mocked_repo.create = AsyncMock()
    mocked_repo_class.return_value = mocked_repo

    data = CreateBehaviorInput(
        name=name, code="def decide_action():\n    pass", kind="player"
    )
    with pytest.raises(HTTPException) as exc_info:
        await BehaviorApiImpl(MagicMock()).create_behavior(data, club_id)

    assert exc_info.value.status_code == 400
    mocked_validate.assert_not_called()  # No debe ser llamado porque agarra el error pydantic
    mocked_repo.create.assert_not_called()


@pytest.mark.parametrize("name", ["Atacante", "  Atacante  ", "Atacante\n"])
@patch("app.impl.behavior_api_impl.validate_behavior_code")
@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_create_behavior_name_use(mocked_repo_class, mocked_validate, name):
    club_id = uuid.uuid4()
    mocked_repo = MagicMock()
    mocked_repo.create = AsyncMock(side_effect=DuplicateNameBehavior())
    mocked_repo_class.return_value = mocked_repo

    data = CreateBehaviorInput(
        name=name, code="def decide_action():\n    pass", kind="player"
    )
    with pytest.raises(HTTPException) as exc_info:
        await BehaviorApiImpl(MagicMock()).create_behavior(data, club_id)

    assert exc_info.value.status_code == 409
    mocked_validate.assert_called_once_with(
        "def decide_action():\n    pass", "player"
    )  # validate_code no es async.
    mocked_repo.create.assert_awaited_once_with(  # create si es async.
        club_id, "Atacante", "def decide_action():\n    pass", "player"
    )


@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_create_behavior_name_31_char(mocked_repo_class):
    club_id = uuid.uuid4()
    mocked_repo = MagicMock()
    mocked_repo.create = AsyncMock()
    mocked_repo_class.return_value = mocked_repo

    data = CreateBehaviorInput(
        name="CorrerCorrerCorrerCorrerCorrer1",
        code="def decide_action():\n    pass",
        kind="player",
    )
    with pytest.raises(HTTPException) as exc_info:
        await BehaviorApiImpl(MagicMock()).create_behavior(data, club_id)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Los caracteres ingresados son invalidos"


@patch("app.impl.behavior_api_impl.validate_behavior_code")
@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_create_behavior_invalid_code(mocked_repo_class, mocked_validate):
    club_id = uuid.uuid4()
    code = "def decide_action():"  # codigo invalido
    mocked_repo = MagicMock()
    mocked_repo.create = AsyncMock(side_effect=InvalidBehaviorCode)
    mocked_repo_class.return_value = mocked_repo
    mocked_validate.side_effect = InvalidBehaviorCode("Línea 3: no se permite import")

    data = CreateBehaviorInput(
        name="CorrerCorrerCorrerCorrerCorrer", code=code, kind="player"
    )
    with pytest.raises(HTTPException) as exc_info:
        await BehaviorApiImpl(MagicMock()).create_behavior(data, club_id)

    assert exc_info.value.status_code == 400
    mocked_validate.assert_called_once_with(code, "player")
    mocked_repo.create.assert_not_called()  # chequeo que no se llama el create


@patch("app.impl.behavior_api_impl.validate_behavior_code")
@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_create_behavior_coach(mocked_repo_class, mocked_validate):
    club_id = uuid.uuid4()
    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id=behavior_id,
        name="CorrerCorrerCorrerCorrerCorrer",
        code="def decide_coach():\n    pass",
        club_id=club_id,
        kind="coach",
    )
    mocked_repo = MagicMock()
    mocked_repo.create = AsyncMock(return_value=behavior_db)
    mocked_repo_class.return_value = mocked_repo

    data = CreateBehaviorInput(
        name="CorrerCorrerCorrerCorrerCorrer",
        code="def decide_coach():\n    pass",
        kind="coach",
    )
    result = await BehaviorApiImpl(MagicMock()).create_behavior(data, club_id)

    assert result.id == behavior_id
    assert result.name == "CorrerCorrerCorrerCorrerCorrer"
    assert result.code == "def decide_coach():\n    pass"
    assert result.kind == "coach"

    mocked_validate.assert_called_once_with(
        "def decide_coach():\n    pass", "coach"
    )  # verifico que valido con el codigo y con el kind correctos
    mocked_repo.create.assert_awaited_once_with(
        club_id,
        "CorrerCorrerCorrerCorrerCorrer",
        "def decide_coach():\n    pass",
        "coach",
    )

@patch("app.impl.behavior_api_impl.validate_behavior_code")
@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_update_behavior_succes(mocked_repo_class, mocked_validate):
    club_id = uuid.uuid4()
    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id=behavior_id,
        name="CorrerCorrerCorrerCorrerCorrer",
        code="def decide_coach():\n    pass",
        club_id=club_id,
        kind="coach",
    )
    mocked_repo = MagicMock()
    mocked_repo.get_id_and_club = AsyncMock(return_value=behavior_db)
    mocked_repo.is_assigned = AsyncMock(return_value=False)
    
    async def fake_update(behavior_id, club_id, name, code):
        behavior_db.name = name
        behavior_db.code = code
        return behavior_db

    mocked_repo.update = AsyncMock(side_effect=fake_update) #reemplazo el update por el fake_update
    mocked_repo_class.return_value = mocked_repo

    data = UpdateBehaviorInput(name="Gallardo", code="def decide_coach():\n    x = 1")
    result = await BehaviorApiImpl(MagicMock()).update_behavior(behavior_id, data, club_id)

    assert result.name == "Gallardo"
    assert result.code == "def decide_coach():\n    x = 1"
    assert result.kind == "coach"
    assert result.id == behavior_id

    mocked_validate.assert_called_once_with(data.code, "coach")
    mocked_repo.update.assert_awaited_once_with(
        behavior_id, club_id, "Gallardo", data.code
    )

@patch("app.impl.behavior_api_impl.validate_behavior_code")
@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_update_not_behavior(mocked_repo_class, mocked_validate):
    club_id = uuid.uuid4()
    behavior_id = uuid.uuid4()
    behavior_db = None
    mocked_repo = MagicMock()
    mocked_repo.get_id_and_club = AsyncMock(return_value=behavior_db)
    mocked_repo.is_assigned = AsyncMock(return_value=False)

    async def fake_update(behavior_id, club_id, name, code):
            behavior_db.name = name
            behavior_db.code = code
            return behavior_db

    mocked_repo.update = AsyncMock(side_effect=fake_update) #reemplazo el update por el fake_update
    mocked_repo_class.return_value = mocked_repo

    data = UpdateBehaviorInput(name="Gallardo", code="def decide_coach():\n    x = 1")
    with pytest.raises(HTTPException) as exc_info:
        await BehaviorApiImpl(MagicMock()).update_behavior(behavior_id, data, club_id)

    assert exc_info.value.status_code == 404
    mocked_repo.update.assert_not_called()


@patch("app.impl.behavior_api_impl.validate_behavior_code")
@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_update_behavior_invalid_name(mocked_repo_class, mocked_validate):
    club_id = uuid.uuid4()
    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id=behavior_id,
        name="CorrerCorrerCorrerCorrerCorrer",
        code="def decide_coach():\n    pass",
        club_id=club_id,
        kind="coach",
    )
    mocked_repo = MagicMock()
    mocked_repo.get_id_and_club = AsyncMock(return_value=behavior_db)
    mocked_repo.is_assigned = AsyncMock(return_value=False)
    
    async def fake_update(behavior_id, club_id, name, code):
        behavior_db.name = name
        behavior_db.code = code
        return behavior_db

    mocked_repo.update = AsyncMock(side_effect=fake_update) #reemplazo el update por el fake_update
    mocked_repo_class.return_value = mocked_repo

    data = UpdateBehaviorInput(name="GallardoGallardoGallardoGallardo", code="def decide_coach():\n    x = 1")
    with pytest.raises(HTTPException) as exc_info:
        await BehaviorApiImpl(MagicMock()).update_behavior(behavior_id, data, club_id)

    assert exc_info.value.status_code == 400
    mocked_repo.update.assert_not_called()

@patch("app.impl.behavior_api_impl.validate_behavior_code")
@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_update_behavior_name_use(mocked_repo_class, mocked_validate):
    club_id = uuid.uuid4()
    behavior_id = uuid.uuid4
    behavior_db = BehaviorDB(
        id=behavior_id,
        name="CorrerCorrerCorrerCorrerCorrer",
        code="def decide_coach():\n    pass",
        club_id=club_id,
        kind="coach",
    )
    mocked_repo = MagicMock()
    mocked_repo.get_id_and_club = AsyncMock(return_value=behavior_db)
    mocked_repo.is_assigned = AsyncMock(return_value=False)
    mocked_repo.update = AsyncMock(side_effect=DuplicateNameBehavior())
    mocked_repo_class.return_value = mocked_repo

    data = UpdateBehaviorInput(name="Gallardo", code="def decide_coach():\n    x = 1")
    with pytest.raises(HTTPException) as exc_info:
        await BehaviorApiImpl(MagicMock()).update_behavior(behavior_id, data, club_id)

    assert exc_info.value.status_code == 409
    mocked_repo.update.assert_awaited_once_with(behavior_id, club_id, "Gallardo", data.code)


@patch("app.impl.behavior_api_impl.validate_behavior_code")
@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_update_behavior_invalid_code(mocked_repo_class, mocked_validate):
    club_id = uuid.uuid4()
    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id=behavior_id,
        name="CorrerCorrerCorrerCorrerCorrer",
        code="def decide_coach():\n    pass",
        club_id=club_id,
        kind="coach",
    )
    mocked_repo = MagicMock()
    mocked_repo.get_id_and_club = AsyncMock(return_value=behavior_db)
    mocked_repo.is_assigned = AsyncMock(return_value=False)
    mocked_repo.update = AsyncMock()
    mocked_repo_class.return_value = mocked_repo
    mocked_validate.side_effect = InvalidBehaviorCode("Línea 3: no se permite import")

    data = UpdateBehaviorInput(name="Gallardo", code="def:\n    x = 1")
    with pytest.raises(HTTPException) as exc_info:
        await BehaviorApiImpl(MagicMock()).update_behavior(behavior_id, data, club_id)

    assert exc_info.value.status_code == 400
    mocked_validate.assert_called_once_with(data.code, "coach")
    mocked_repo.update.assert_not_called()  

@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_delete_behavior_succes(mocked_repo_class):
    club_id = uuid.uuid4()
    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id=behavior_id,
        name="Gambetear",
        code="def decide_action():\n    pass",
        club_id=club_id,
        kind="player",
    )
    mocked_repo = MagicMock()
    mocked_repo.get_id_and_club = AsyncMock(return_value=behavior_id)
    mocked_repo.is_assigned = AsyncMock(return_value = False)
    mocked_repo.delete = AsyncMock()
    mocked_repo_class.return_value = mocked_repo

    result = await BehaviorApiImpl(MagicMock()).delete_behavior(behavior_db, club_id)

    assert result is None

@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_delete_behavior_is_assigned(mocked_repo_class):
    club_id = uuid.uuid4()
    behavior_id = uuid.uuid4()
    behavior_db = BehaviorDB(
        id=behavior_id,
        name="Gambetear",
        code="def decide_action():\n    pass",
        club_id=club_id,
        kind="player",
    )
    mocked_repo = MagicMock()
    mocked_repo.get_id_and_club = AsyncMock(return_value=behavior_id)
    mocked_repo.is_assigned = AsyncMock(return_value = True)
    mocked_repo.delete = AsyncMock()
    mocked_repo_class.return_value = mocked_repo
    with pytest.raises(HTTPException) as exc_info:
        await BehaviorApiImpl(MagicMock()).delete_behavior(behavior_db, club_id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "El comportamiento esta siendo utilizado en una alineación, debes reemplazarlo para poder eliminarlo"
    mocked_repo.delete.assert_not_called() 

@patch("app.impl.behavior_api_impl.BehaviorRepository")
async def test_delete_behavior_not_exist(mocked_repo_class):
    club_id = uuid.uuid4()
    behavior_db = BehaviorDB()
    mocked_repo = MagicMock()
    mocked_repo.get_id_and_club = AsyncMock(return_value=None)
    mocked_repo.is_assigned = AsyncMock(return_value = False)
    mocked_repo.delete = AsyncMock()
    mocked_repo_class.return_value = mocked_repo
    with pytest.raises(HTTPException) as exc_info:
        await BehaviorApiImpl(MagicMock()).delete_behavior(behavior_db, club_id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "El comportamiento no existe"
    mocked_repo.delete.assert_not_called()
