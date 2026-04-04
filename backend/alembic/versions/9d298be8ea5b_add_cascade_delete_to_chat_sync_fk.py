"""add_cascade_delete_to_chat_sync_fk

Revision ID: 9d298be8ea5b
Revises: 991d00bf78d6
Create Date: 2023-03-15 18:05:13.764962

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9d298be8ea5b"
down_revision = "991d00bf78d6"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the existing constraint
    op.drop_constraint("chat_sync_id_fkey", "chat", type_="foreignkey")

    # Re-create the constraint with ON DELETE CASCADE
    op.create_foreign_key(
        "chat_sync_id_fkey", "chat", "sync", ["sync_id"], ["id"], ondelete="CASCADE"
    )


def downgrade():
    # Drop the CASCADE constraint
    op.drop_constraint("chat_sync_id_fkey", "chat", type_="foreignkey")

    # Re-create the original constraint without CASCADE
    op.create_foreign_key("chat_sync_id_fkey", "chat", "sync", ["sync_id"], ["id"])
