# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from typing import List
from app.models.error import Error
from app.models.ranking_item import RankingItem
from app.security_api import get_token_bearerAuth

class BaseRankingApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseRankingApi.subclasses = BaseRankingApi.subclasses + (cls,)
    async def get_ranking(
        self,
    ) -> List[RankingItem]:
        """Calculado a partir de los partidos jugados en instancias públicas (ligas públicas y amistosos)."""
        ...
