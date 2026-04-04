"""Remove minute_level_cron_schedule from sync table

Revision ID: c60291fb2129
Revises: c3d4e5f6g7h8
Create Date: 2025-09-25 11:41:34.343624

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c60291fb2129"
down_revision = "c3d4e5f6g7h8"
branch_labels = None
depends_on = None


def upgrade():
    """
    Unify CRON schedule fields by migrating minute_level_cron_schedule to cron_schedule
    and then removing the minute_level_cron_schedule column.
    """

    # Step 1: Migrate existing minute_level_cron_schedule values to cron_schedule
    # For any syncs that have minute_level_cron_schedule but no cron_schedule
    op.execute(
        """
        UPDATE sync
        SET cron_schedule = minute_level_cron_schedule,
            sync_type = 'incremental'
        WHERE minute_level_cron_schedule IS NOT NULL
          AND cron_schedule IS NULL
    """
    )

    # Step 2: Handle conflicts where both fields are set
    # Prefer minute_level_cron_schedule as it was more specific
    op.execute(
        """
        UPDATE sync
        SET cron_schedule = minute_level_cron_schedule,
            sync_type = 'incremental'
        WHERE minute_level_cron_schedule IS NOT NULL
          AND cron_schedule IS NOT NULL
    """
    )

    # Step 3: Update sync_type for existing cron_schedule entries
    # Set to incremental for minute-level patterns (*/N where N < 60)
    op.execute(
        """
        UPDATE sync
        SET sync_type = 'incremental'
        WHERE cron_schedule ~ '^(\\*/[1-5]?[0-9]|[0-5]?[0-9]) \\* \\* \\* \\*$'
          AND (
              cron_schedule ~ '^\\*/([1-9]|[1-5][0-9]) \\* \\* \\* \\*$'
              OR cron_schedule ~ '^[0-5]?[0-9] \\* \\* \\* \\*$'
          )
    """
    )

    # Step 4: Drop the minute_level_cron_schedule column
    op.drop_column("sync", "minute_level_cron_schedule")


def downgrade():
    """
    Restore minute_level_cron_schedule column and migrate incremental syncs back to it.
    """

    # Step 1: Re-add the minute_level_cron_schedule column
    op.add_column(
        "sync",
        sa.Column(
            "minute_level_cron_schedule", sa.VARCHAR(length=100), autoincrement=False, nullable=True
        ),
    )

    # Step 2: Migrate minute-level schedules back to minute_level_cron_schedule
    # Move schedules that are minute-level patterns (*/N where N < 60) for incremental syncs
    op.execute(
        """
        UPDATE sync
        SET minute_level_cron_schedule = cron_schedule,
            cron_schedule = NULL
        WHERE sync_type = 'incremental'
          AND cron_schedule ~ '^(\\*/[1-5]?[0-9]|[0-5]?[0-9]) \\* \\* \\* \\*$'
          AND (
              cron_schedule ~ '^\\*/([1-9]|[1-5][0-9]) \\* \\* \\* \\*$'
              OR cron_schedule ~ '^[0-5]?[0-9] \\* \\* \\* \\*$'
          )
    """
    )
