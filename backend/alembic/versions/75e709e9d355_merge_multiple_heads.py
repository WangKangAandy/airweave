"""Merge multiple heads

Revision ID: 75e709e9d355
Revises: 94cba0badfd8, c6724d75676a
Create Date: 2025-06-19 16:30:30.603985

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "75e709e9d355"
down_revision = ("94cba0badfd8", "c6724d75676a")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
