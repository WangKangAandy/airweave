"""add_connection_id_to_source_connection

Revision ID: a8b2c3d4e5f6
Revises: 210e475985ae
Create Date: 2025-05-06 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a8b2c3d4e5f6"
down_revision = "210e475985ae"
branch_labels = None
depends_on = None


def upgrade():
    # Add connection_id column to the source_connection table
    op.add_column("source_connection", sa.Column("connection_id", sa.UUID(), nullable=True))

    # Add foreign key constraint to the connection table
    op.create_foreign_key(
        "fk_source_connection_connection_id",
        "source_connection",
        "connection",
        ["connection_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    # Drop the foreign key constraint first
    op.drop_constraint(
        "fk_source_connection_connection_id", "source_connection", type_="foreignkey"
    )

    # Drop the connection_id column
    op.drop_column("source_connection", "connection_id")
