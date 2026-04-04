"""Add CASCADE delete to user_organization foreign keys

Revision ID: c61f1307be00
Revises: 7dfef9ba17c0
Create Date: 2025-06-10 20:29:30.506921

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c61f1307be00"
down_revision = "7dfef9ba17c0"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
