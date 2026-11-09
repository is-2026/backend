import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeagueStandingsDB(Base):
    __tablename__ = "league_standings"
    __table_args__ = (
        UniqueConstraint("league_id", "rank"),
    )  # unicidad de ranking (i.e. dos clubes no pueden compartir la misma posicion en la tabla de una liga)
    # tener en cuenta al momento de recalcular posiciones, podria haber ranks duplicados intermedios durante el UPDATE

    # PK compuesta: league_id+club_id
    league_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leagues.id"), primary_key=True
    )
    club_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clubs.id"), primary_key=True)

    rank: Mapped[int] = mapped_column(nullable=False)
    # todas las estadisticas inicializan en 0
    points: Mapped[int] = mapped_column(default=0)
    matches_played: Mapped[int] = mapped_column(default=0)
    won: Mapped[int] = mapped_column(default=0)
    won_penalties: Mapped[int] = mapped_column(default=0)
    drawn: Mapped[int] = mapped_column(default=0)
    lost: Mapped[int] = mapped_column(default=0)
    goals_dif: Mapped[int] = mapped_column(default=0)
    goals_for: Mapped[int] = mapped_column(default=0)
    goals_against: Mapped[int] = mapped_column(default=0)
