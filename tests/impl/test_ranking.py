import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.club import ClubDB
from app.db.league import LeagueDB
from app.db.standings import LeagueStandingsDB
from app.db.user import UserDB
from app.impl.ranking_api_impl import RankingApiImpl, sort_standings
from app.repositories.league_repository import ClubRankingTotals
from app.security.tokens import create_access_token

URL = "/ranking"


# --- sort_standings ---


# arma un club de prueba con nombre, puntos y goles, para pasarle a sort_standings
def row(name, points=0, goals_for=0, goals_against=0):
    return SimpleNamespace(
        club_name=name, points=points, goals_for=goals_for, goals_against=goals_against
    )


# devuelve solo los nombres, para ver en que orden quedaron
def names(rows):
    return [r.club_name for r in rows]


# A tiene 3 puntos, B 9 y C 6: tiene que quedar B, C, A
def test_sort_standings_by_points():
    rows = [row("A", points=3), row("B", points=9), row("C", points=6)]
    assert names(sort_standings(rows)) == ["B", "C", "A"]


# A y B tienen 6 puntos, pero B tiene mejor diferencia de gol: B va primero
def test_sort_standings_tie_by_goal_difference():
    rows = [
        row("A", 6, goals_for=5, goals_against=4),  # diferencia +1
        row("B", 6, goals_for=5, goals_against=1),  # diferencia +4
    ]
    assert names(sort_standings(rows)) == ["B", "A"]


# A y B tienen 6 puntos y +2 de diferencia, pero B hizo mas goles: B va primero
def test_sort_standings_tie_by_goals_for():
    rows = [
        row("A", 6, goals_for=3, goals_against=1),  # 3 goles
        row("B", 6, goals_for=7, goals_against=5),  # 7 goles
    ]
    assert names(sort_standings(rows)) == ["B", "A"]


# los tres estan igualados en todo: quedan en orden alfabetico
def test_sort_standings_tie_by_name():
    rows = [row("racing"), row("Boca"), row("independiente")]
    assert names(sort_standings(rows)) == ["Boca", "independiente", "racing"]


# --- get_ranking ---


# arma los datos de un club como si vinieran de la base
def totals(name, points):
    return ClubRankingTotals(
        club_id=uuid.uuid4(), club_name=name, avatar_url="https://img.com/a.png",
        points=points, matches_played=1, won=0, won_penalties=0, drawn=0, lost=0,
        goals_for=0, goals_against=0,
    )


# reemplazamos la base por datos falsos: Belgrano 3, Instituto 9, Talleres 6
# get_ranking tiene que devolver Instituto 1, Talleres 2, Belgrano 3
@patch("app.impl.ranking_api_impl.LeagueRepository")
async def test_get_ranking_sorted_with_positions(mocked_repo_class):
    mocked_repo = MagicMock()
    mocked_repo.list_ranking_totals = AsyncMock(
        return_value=[totals("Belgrano", 3), totals("Instituto", 9), totals("Talleres", 6)]
    )
    mocked_repo_class.return_value = mocked_repo

    result = await RankingApiImpl(MagicMock()).get_ranking()

    assert [(r.position, r.club_name) for r in result] == [
        (1, "Instituto"), (2, "Talleres"), (3, "Belgrano"),
    ]


# --- tests de endpoint ---


# arma el header con un token valido, como el que manda el front
def auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(uuid.uuid4())}"}


# pedimos /ranking sin token: tiene que responder 401
async def test_endpoint_ranking_without_token_returns_401(client):
    r = await client.get(URL)
    assert r.status_code == 401
    assert "No autorizado" in r.json()["message"]


# pedimos /ranking con token pero sin ninguna liga cargada: tiene que responder 200 y []
async def test_endpoint_ranking_empty_returns_200(client):
    r = await client.get(URL, headers=auth_header())
    assert r.status_code == 200
    assert r.json() == []


# cargamos un club con 4 puntos en una liga publica y pedimos /ranking:
# tiene que venir ese club en el 1 puesto, con todos sus datos
async def test_endpoint_ranking_returns_all_fields(client, session):
    user_id, club_id, league_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    session.add(UserDB(id=user_id, email="r@test.com", hashed_password="hash"))
    await session.flush()
    session.add(ClubDB(id=club_id, club_name="Instituto",
                       avatar_url="https://img.com/a.png", user_id=user_id))
    await session.flush()
    session.add(LeagueDB(id=league_id, name="Liga", hashed_password=None, max_clubs=5,
                         match_duration_minutes=10, status="started", creator_club_id=club_id))
    await session.flush()
    session.add(LeagueStandingsDB(league_id=league_id, club_id=club_id, rank=1, points=4,
                                  matches_played=2, won=1, won_penalties=0, drawn=1,
                                  lost=0, goals_for=3, goals_against=1))
    await session.commit()

    r = await client.get(URL, headers=auth_header())

    assert r.status_code == 200
    assert r.json() == [{
        "position": 1, "club_id": str(club_id), "club_name": "Instituto",
        "avatar_url": "https://img.com/a.png", "points": 4, "matches_played": 2,
        "won": 1, "won_penalties": 0, "drawn": 1, "lost": 0,
        "goals_for": 3, "goals_against": 1,
    }]