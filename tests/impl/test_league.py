import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.impl import league_api_impl
from app.impl.league_api_impl import LeaguesApiImpl
from app.models.create_league_input import CreateLeagueInput
from app.models.squad_player_input import SquadPlayerInput

CLUB = SimpleNamespace(id=uuid.uuid4(), club_name="River")


def make_input(starters=3, password=None):
    players = [
        SquadPlayerInput(
            player_id=uuid.uuid4(),
            is_starter=i < starters,
            behavior_id=uuid.uuid4() if i < starters else None,
        )
        for i in range(6)
    ]
    return CreateLeagueInput(
        name="Liga", password=password, max_clubs=5,
        match_duration_minutes=10, players=players,
    )


@pytest.fixture
def mocks(monkeypatch):
    m = SimpleNamespace()
    m.session = MagicMock()
    # session.get devuelve un comportamiento que es del club
    m.session.get = AsyncMock(return_value=SimpleNamespace(club_id=CLUB.id))
    m.player_repo = AsyncMock()
    m.player_repo.count_club_players.return_value = 6  # los 6 son del club
    m.league_repo = AsyncMock()
    m.league_repo.create_with_enrollment.return_value = SimpleNamespace(
        id=uuid.uuid4(), name="Liga", hashed_password=None,
        max_clubs=5, status="not_started",
    )
    m.hash_password = AsyncMock(return_value="hashed")

    monkeypatch.setattr(league_api_impl, "PlayerRepository", MagicMock(return_value=m.player_repo))
    monkeypatch.setattr(league_api_impl, "LeagueRepository", MagicMock(return_value=m.league_repo))
    monkeypatch.setattr(league_api_impl, "hash_password", m.hash_password)
    return m


@pytest.fixture
def api(mocks):
    return LeaguesApiImpl(mocks.session)


async def test_create_league_public(api, mocks):
    result = await api.create_league(make_input(), CLUB)

    mocks.hash_password.assert_not_awaited()  # sin password no se hashea
    assert result.is_private is False
    assert result.status == "not_started"
    # el creador queda inscripto
    assert result.registered_clubs[0].club_id == CLUB.id
    assert result.registered_clubs[0].club_name == "River"
    assert mocks.league_repo.create_with_enrollment.await_args.kwargs["club_id"] == CLUB.id


async def test_create_league_private(api, mocks):
    mocks.league_repo.create_with_enrollment.return_value.hashed_password = "hashed"

    result = await api.create_league(make_input(password="1234"), CLUB)

    mocks.hash_password.assert_awaited_once_with("1234")
    assert result.is_private is True


@pytest.mark.parametrize("starters", [2, 4])
async def test_create_league_wrong_number_of_starters(api, mocks, starters):
    with pytest.raises(HTTPException) as error:
        await api.create_league(make_input(starters=starters), CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_starter_without_behavior(api, mocks):
    data = make_input()
    data.players[0].behavior_id = None

    with pytest.raises(HTTPException) as error:
        await api.create_league(data, CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_repeated_players(api, mocks):
    data = make_input()
    data.players[1].player_id = data.players[0].player_id

    with pytest.raises(HTTPException) as error:
        await api.create_league(data, CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_players_other_club(api, mocks):
    mocks.player_repo.count_club_players.return_value = 5  # uno no es del club

    with pytest.raises(HTTPException) as error:
        await api.create_league(make_input(), CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_behavior_other_club(api, mocks):
    mocks.session.get.return_value = SimpleNamespace(club_id=uuid.uuid4())  # club ajeno

    with pytest.raises(HTTPException) as error:
        await api.create_league(make_input(), CLUB)

    assert error.value.status_code == 400
    mocks.league_repo.create_with_enrollment.assert_not_awaited()


async def test_create_league_behavior_not_exist(api, mocks):
    mocks.session.get.return_value = None

    with pytest.raises(HTTPException) as error:
        await api.create_league(make_input(), CLUB)

    assert error.value.status_code == 400


async def test_create_league_repo_integrity_error(api, mocks):
    mocks.league_repo.create_with_enrollment.side_effect = IntegrityError("INSERT", {}, Exception("fk"))

    with pytest.raises(HTTPException) as error:
        await api.create_league(make_input(), CLUB)

    assert error.value.status_code == 400