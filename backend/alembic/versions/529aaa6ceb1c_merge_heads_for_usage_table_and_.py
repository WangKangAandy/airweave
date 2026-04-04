"""merge heads for usage table and trialing status

Revision ID: 529aaa6ceb1c
Revises: 3c0d6c431e21, 3d49312c98fd
Create Date: 2025-07-26 09:16:04.306408

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '529aaa6ceb1c'
down_revision = ('3c0d6c431e21', '3d49312c98fd')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
