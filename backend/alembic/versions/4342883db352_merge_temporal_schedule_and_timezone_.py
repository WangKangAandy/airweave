"""merge temporal schedule and timezone conversion branches

Revision ID: 4342883db352
Revises: 01538fc19202, 478587386b42
Create Date: 2025-08-15 13:33:50.288689

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4342883db352'
down_revision = ('01538fc19202', '478587386b42')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
