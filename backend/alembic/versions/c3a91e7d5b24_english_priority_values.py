"""Store task priorities with English values

Data-only revision: the schema does not change.

Upgrade maps the Italian priorities 'media', 'alta' and 'bassa' of tasks.priority
to 'medium', 'high' and 'low', ignoring case and surrounding spaces. Every other
value (English values, NULL, empty or unexpected strings) is left as it is.

Downgrade applies the inverse mapping ('medium' -> 'media', 'high' -> 'alta',
'low' -> 'bassa'). The database does not record which rows the upgrade changed,
so rows that were already English before the upgrade (set from the UI) also
become Italian on downgrade.

Revision ID: c3a91e7d5b24
Revises: fb815bf08509
Create Date: 2026-11-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a91e7d5b24'
down_revision: Union[str, Sequence[str], None] = 'fb815bf08509'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade data: Italian priority values become English."""
    op.execute(sa.text(
        "UPDATE tasks SET priority = CASE lower(trim(priority)) "
        "WHEN 'media' THEN 'medium' "
        "WHEN 'alta' THEN 'high' "
        "WHEN 'bassa' THEN 'low' "
        "END "
        "WHERE lower(trim(priority)) IN ('media', 'alta', 'bassa')"
    ))


def downgrade() -> None:
    """Downgrade data: English priority values become Italian."""
    op.execute(sa.text(
        "UPDATE tasks SET priority = CASE priority "
        "WHEN 'medium' THEN 'media' "
        "WHEN 'high' THEN 'alta' "
        "WHEN 'low' THEN 'bassa' "
        "END "
        "WHERE priority IN ('medium', 'high', 'low')"
    ))
