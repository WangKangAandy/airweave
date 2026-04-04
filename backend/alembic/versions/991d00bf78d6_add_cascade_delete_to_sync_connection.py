"""add_cascade_delete_to_sync_connection

Revision ID: 991d00bf78d6
Revises: 97758b0549eb
Create Date: 2025-03-15 17:34:26.905123

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "991d00bf78d6"
down_revision = "97758b0549eb"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the existing constraint
    op.drop_constraint("sync_connection_sync_id_fkey", "sync_connection", type_="foreignkey")

    # Re-create the constraint with ON DELETE CASCADE
    op.create_foreign_key(
        "sync_connection_sync_id_fkey",
        "sync_connection",
        "sync",
        ["sync_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    # Drop the CASCADE constraint
    op.drop_constraint("sync_connection_sync_id_fkey", "sync_connection", type_="foreignkey")

    # Re-create the original constraint without CASCADE
    op.create_foreign_key(
        "sync_connection_sync_id_fkey", "sync_connection", "sync", ["sync_id"], ["id"]
    )
