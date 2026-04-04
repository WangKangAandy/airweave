"""add_cursor_field_to_sync_cursor

Revision ID: aafff4b827f4
Revises: 4342883db352
Create Date: 2025-08-19 15:23:51.993438

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aafff4b827f4'
down_revision = '4342883db352'
branch_labels = None
depends_on = None


def upgrade():
    """Add cursor_field column to sync_cursor table."""
    op.add_column('sync_cursor', sa.Column('cursor_field', sa.String(), nullable=True))


def downgrade():
    """Remove cursor_field column from sync_cursor table."""
    op.drop_column('sync_cursor', 'cursor_field')
