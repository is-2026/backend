import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlayerDB(Base):
    __tablename__ = "players"
    __table_args__ = (
        # el número de camiseta es único dentro de cada club
        UniqueConstraint("club_id", "number", name="uq_players_club_id_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    # PACSS
    power: Mapped[int] = mapped_column(Integer, nullable=False)
    agility: Mapped[int] = mapped_column(Integer, nullable=False)
    control: Mapped[int] = mapped_column(Integer, nullable=False)
    speed: Mapped[int] = mapped_column(Integer, nullable=False)
    strength: Mapped[int] = mapped_column(Integer, nullable=False)

    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id"), nullable=False, index=True
    )
