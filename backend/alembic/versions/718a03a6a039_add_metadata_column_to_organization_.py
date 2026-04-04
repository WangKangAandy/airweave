"""Add metadata column to organization table

Revision ID: 718a03a6a039
Revises: add_billing_tables
Create Date: 2025-07-25 10:08:05.083732

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "718a03a6a039"
down_revision = "add_billing_tables"
branch_labels = None
depends_on = None


def upgrade():
    # Add org_metadata column to organization table
    op.add_column("organization", sa.Column("org_metadata", postgresql.JSON(), nullable=True))


def downgrade():
    # Remove org_metadata column from organization table
    op.drop_column("organization", "org_metadata")
