"""add_next_scheduled_run_to_sync

Revision ID: 2a6c65061d05
Revises: 86c0732b1e07
Create Date: 2025-03-12 15:58:59.442253

"""

from datetime import datetime, timezone
from typing import List, Tuple

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Column, String, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

# Try to import croniter, but don't fail if it's not available
try:
    from croniter import croniter

    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False


# revision identifiers, used by Alembic.
revision = "2a6c65061d05"
down_revision = "86c0732b1e07"
branch_labels = None
depends_on = None


def upgrade():
    # Add next_scheduled_run column to sync table
    op.add_column(
        "sync", sa.Column("next_scheduled_run", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade():
    # Remove next_scheduled_run column from sync table
    op.drop_column("sync", "next_scheduled_run")
