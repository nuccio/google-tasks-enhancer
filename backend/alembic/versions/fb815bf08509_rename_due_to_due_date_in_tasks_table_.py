"""Rename 'due' to 'due_date' in tasks table (manual)

Revision ID: fb815bf08509
Revises: 24962bbb8f9a
Create Date: 2026-04-20 22:10:46.934473

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb815bf08509'
down_revision: Union[str, Sequence[str], None] = '24962bbb8f9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.alter_column('due', new_column_name='due_date', existing_type=sa.String(), existing_nullable=True)

def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.alter_column('due_date', new_column_name='due', existing_type=sa.String(), existing_nullable=True)
