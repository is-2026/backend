import uuid

from sqlalchemy import ForeignKey, String, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class FriendlyDB(Base):
    __tablename__ = "friendlies"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )

    creator_club_id : Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id"), nullable= False
    )

    rival_club_id : Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id"), nullable= True
    )

    hashed_password : Mapped[str] = mapped_column(String(255), nullable=True)

    status : Mapped[str] = mapped_column(String(200), default="waiting_for_rival")

    match_id : Mapped[uuid.UUID] = mapped_column(
        nullable= True #Poner FK cuando tengamos tabla de partidos.
    )

class FriendlyPlayerDB(Base):
    __tablename__ = "friendly_players"
    __table_args__ = (UniqueConstraint("friendly_id", "player_id", name="uq_friendly_player"),) #1 pl, no puede estar 2 vec en el mismo part
 
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, index=True
    )

    friendly_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("friendlies.id"), nullable= False
    )

    club_id : Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id"), nullable= False
    )

    player_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("players.id"), nullable= False
    )

    is_starter : Mapped[bool] = mapped_column(Boolean, nulable=False)

    behavior_id : Mapped[uuid.UUID] = mapped_column(
        ForeignKey("behaviors.id"), nullable= True
    )