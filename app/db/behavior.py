import uuid

from sqlalchemy import ForeignKey, Text, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class BehaviorDB(Base):
    __tablename__= "behaviors"

    # el nombre del comportamiento es unico por club
    __table_args__ = (
        UniqueConstraint("club_id", "name", name="uq_behavior_club_id_name"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, 
        default=uuid.uuid4, 
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(30), 
        nullable=False
    )

    # tipo Text, mas apropiado para codigo, longitud variable
    code: Mapped[str] = mapped_column( 
        Text,
        nullable=False
    )
    club_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clubs.id"), 
        nullable=False, 
        index=True
    )
    kind : Mapped[str] = mapped_column(
        default = "player",
        server_default = "player",
        nullable = False,        
    )