"""Add supports_continuous field to source table

Revision ID: c3d4e5f6g7h8
Revises: 264fdc0ac89c
Create Date: 2025-09-25 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6g7h8"
down_revision: Union[str, None] = "264fdc0ac89c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add supports_continuous column to source table."""
    op.add_column(
        "source",
        sa.Column("supports_continuous", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    """Remove supports_continuous column from source table."""
    op.drop_column("source", "supports_continuous")
