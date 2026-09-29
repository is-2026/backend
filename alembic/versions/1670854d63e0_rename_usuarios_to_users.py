"""rename usuarios to users

Revision ID: 1670854d63e0
Revises: 895d017f6a2b
Create Date: 2026-09-29 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1670854d63e0'
down_revision: Union[str, Sequence[str], None] = '895d017f6a2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f('ix_usuarios_id'), table_name='usuarios')
    op.drop_index(op.f('ix_usuarios_email'), table_name='usuarios')
    op.rename_table('usuarios', 'users')
    op.alter_column(
        'users', 'fecha_creacion',
        new_column_name='created_at',
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.text('now()'),
        existing_nullable=False,
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.alter_column(
        'users', 'created_at',
        new_column_name='fecha_creacion',
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.text('now()'),
        existing_nullable=False,
    )
    op.rename_table('users', 'usuarios')
    op.create_index(op.f('ix_usuarios_email'), 'usuarios', ['email'], unique=True)
    op.create_index(op.f('ix_usuarios_id'), 'usuarios', ['id'], unique=False)
