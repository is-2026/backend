"""friendly behavior fk set null

Revision ID: ed1c9998c36e
Revises: a7b51aafddc9
Create Date: 2026-10-27 03:53:53.720553

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ed1c9998c36e'
down_revision: Union[str, Sequence[str], None] = 'a7b51aafddc9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("friendly_players_ibfk_1", "friendly_players", type_="foreignkey")
    op.create_foreign_key(
        "fk_fp_behavior_id",
        "friendly_players",
        "behaviors",
        ["behavior_id"],
        ["id"],
        ondelete="SET NULL",
    )

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_fp_behavior_id", "friendly_players", type_="foreignkey")
    op.create_foreign_key(
        "friendly_players_ibfk_1",
        "friendly_players",
        "behaviors",
        ["behavior_id"],
        ["id"],
    )