"""merge multiple heads

Revision ID: e2819d7d0588
Revises: 1ab50fcb59fb, 9d298be8ea5b
Create Date: 2025-03-15 18:48:56.550596

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2819d7d0588'
down_revision = ('1ab50fcb59fb', '9d298be8ea5b')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
