"""make_status_fields_ephemeral

Revision ID: bf10682f1193
Revises: 1de8ee6ba9e0
Create Date: 2025-05-07 12:29:52.784046

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "bf10682f1193"
down_revision = "1de8ee6ba9e0"
branch_labels = None
depends_on = None


def upgrade():
    # Remove status from source_connection table
    op.drop_column("source_connection", "status")

    # Remove status from collection table
    op.drop_column("collection", "status")


def downgrade():
    # Re-add status to collection table
    op.add_column(
        "collection",
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "PARTIAL ERROR", "NEEDS SOURCE", "ERROR", name="collectionstatus"),
            nullable=False,
            server_default="NEEDS SOURCE",
        ),
    )

    # Re-add status to source_connection table
    op.add_column(
        "source_connection",
        sa.Column(
            "status",
            sa.Enum("active", "in_progress", "failing", name="sourceconnectionstatus"),
            nullable=False,
            server_default="active",
        ),
    )
