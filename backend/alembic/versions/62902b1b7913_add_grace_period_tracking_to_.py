"""Add grace period tracking to organization billing

Revision ID: 62902b1b7913
Revises: 718a03a6a039
Create Date: 2025-01-24 10:10:10.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "62902b1b7913"
down_revision = "718a03a6a039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns for grace period tracking
    op.add_column(
        "organization_billing",
        sa.Column("grace_period_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organization_billing",
        sa.Column("payment_method_added", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "organization_billing",
        sa.Column("billing_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )

    # Remove server default after adding the column
    op.alter_column("organization_billing", "payment_method_added", server_default=None)


def downgrade() -> None:
    # Remove the new columns
    op.drop_column("organization_billing", "billing_metadata")
    op.drop_column("organization_billing", "payment_method_added")
    op.drop_column("organization_billing", "grace_period_ends_at")
