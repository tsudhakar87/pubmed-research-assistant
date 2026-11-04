"""add_source_to_query_papers

Revision ID: b7c2e4f19a3d
Revises: 84e84cfd77a0
Create Date: 2026-11-04 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c2e4f19a3d'
down_revision: Union[str, None] = '84e84cfd77a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('query_papers', sa.Column('source', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('query_papers', 'source')
