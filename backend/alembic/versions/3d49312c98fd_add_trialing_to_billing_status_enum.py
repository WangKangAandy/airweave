"""add trialing to billing status enum

Revision ID: 3d49312c98fd
Revises: 8014a3f5b255
Create Date: 2025-01-25 12:41:09.701470

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3d49312c98fd"
down_revision = "8014a3f5b255"
branch_labels = None
depends_on = None


def upgrade():
    # Add TRIALING to the BillingStatus enum type
    op.execute("ALTER TYPE billingstatus ADD VALUE IF NOT EXISTS 'TRIALING'")


def downgrade():
    # Note: PostgreSQL doesn't support removing values from enums
    # This would require recreating the type and all dependent columns
    pass
