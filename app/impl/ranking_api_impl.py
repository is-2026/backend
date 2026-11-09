from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.ranking_api_base import BaseRankingApi
from app.models.ranking_item import RankingItem
from app.repositories.league_repository import LeagueRepository


def sort_standings(rows: list) -> list:
    # orden: mas puntos, diferencia de gol, goles a favor, nombre del club.
    return sorted(
        rows,
        key=lambda r: (
            -r.points,
            -(r.goals_for - r.goals_against),
            -r.goals_for,
            r.club_name.lower(),
        ),
    )


class RankingApiImpl(BaseRankingApi):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_ranking(self) -> list[RankingItem]:
        totals = await LeagueRepository(self._session).list_ranking_totals()
        ordered = sort_standings(totals)
        return [
            RankingItem(
                position=position,
                club_id=club.club_id,
                club_name=club.club_name,
                avatar_url=club.avatar_url,
                points=club.points,
                matches_played=club.matches_played,
                won=club.won,
                won_penalties=club.won_penalties,
                drawn=club.drawn,
                lost=club.lost,
                goals_for=club.goals_for,
                goals_against=club.goals_against,
            )
            for position, club in enumerate(ordered, start=1)
        ]