"""Add tasklist_id to Task

Revision ID: 24962bbb8f9a
Revises: 123348add1f3
Create Date: 2026-04-19 23:42:19.739789

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24962bbb8f9a'
down_revision: Union[str, Sequence[str], None] = '123348add1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tasklist_id', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_column('tasklist_id')
