"""Fix billing enums and add grace period fields

Revision ID: bef4ae2f8131
Revises: 62902b1b7913
Create Date: 2025-01-24 10:10:10.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "bef4ae2f8131"
down_revision: Union[str, None] = "62902b1b7913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, create the enum types if they don't exist
    # We'll check if they exist to make this migration idempotent
    connection = op.get_bind()

    # Check if enums exist
    billing_plan_exists = (
        connection.execute(
            sa.text("SELECT 1 FROM pg_type WHERE typname = 'billingplan'")
        ).fetchone()
        is not None
    )

    billing_status_exists = (
        connection.execute(
            sa.text("SELECT 1 FROM pg_type WHERE typname = 'billingstatus'")
        ).fetchone()
        is not None
    )

    payment_status_exists = (
        connection.execute(
            sa.text("SELECT 1 FROM pg_type WHERE typname = 'paymentstatus'")
        ).fetchone()
        is not None
    )

    # Create enums if they don't exist
    if not billing_plan_exists:
        billing_plan_enum = postgresql.ENUM(
            "TRIAL", "DEVELOPER", "STARTUP", "ENTERPRISE", name="billingplan"
        )
        billing_plan_enum.create(connection)

    if not billing_status_exists:
        billing_status_enum = postgresql.ENUM(
            "ACTIVE",
            "PAST_DUE",
            "CANCELED",
            "PAUSED",
            "TRIAL_EXPIRED",
            "GRACE_PERIOD",
            name="billingstatus",
        )
        billing_status_enum.create(connection)

    if not payment_status_exists:
        payment_status_enum = postgresql.ENUM(
            "SUCCEEDED", "FAILED", "PENDING", name="paymentstatus"
        )
        payment_status_enum.create(connection)

    # Now add the new columns if they don't exist
    # Check if columns exist first
    result = connection.execute(
        sa.text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'organization_billing'
            AND column_name IN ('grace_period_ends_at', 'payment_method_added', 'billing_metadata')
        """
        )
    )
    existing_columns = {row[0] for row in result}

    # Add columns that don't exist
    if "grace_period_ends_at" not in existing_columns:
        op.add_column(
            "organization_billing",
            sa.Column("grace_period_ends_at", sa.DateTime(timezone=False), nullable=True),
        )

    if "payment_method_added" not in existing_columns:
        op.add_column(
            "organization_billing",
            sa.Column("payment_method_added", sa.Boolean(), nullable=False, server_default="false"),
        )
        # Remove server default after adding
        op.alter_column("organization_billing", "payment_method_added", server_default=None)

    if "billing_metadata" not in existing_columns:
        op.add_column(
            "organization_billing",
            sa.Column("billing_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        )

    # Convert existing string columns to enums
    # First, update any existing data to match enum values
    op.execute(
        """
        UPDATE organization_billing
        SET billing_plan = UPPER(billing_plan)
        WHERE billing_plan IS NOT NULL
    """
    )

    op.execute(
        """
        UPDATE organization_billing
        SET billing_status = UPPER(billing_status)
        WHERE billing_status IS NOT NULL
    """
    )

    op.execute(
        """
        UPDATE organization_billing
        SET last_payment_status = UPPER(last_payment_status)
        WHERE last_payment_status IS NOT NULL
    """
    )

    # Map old values to new enum values
    op.execute(
        """
        UPDATE organization_billing
        SET billing_plan = 'DEVELOPER'
        WHERE billing_plan = 'developer' OR billing_plan = 'DEVELOPER'
    """
    )

    op.execute(
        """
        UPDATE organization_billing
        SET billing_status = 'ACTIVE'
        WHERE billing_status = 'active' OR billing_status = 'ACTIVE'
    """
    )

    # Now alter the columns to use enums
    op.alter_column(
        "organization_billing",
        "billing_plan",
        type_=postgresql.ENUM("TRIAL", "DEVELOPER", "STARTUP", "ENTERPRISE", name="billingplan"),
        existing_type=sa.String(50),
        postgresql_using="billing_plan::billingplan",
    )

    op.alter_column(
        "organization_billing",
        "billing_status",
        type_=postgresql.ENUM(
            "ACTIVE",
            "PAST_DUE",
            "CANCELED",
            "PAUSED",
            "TRIAL_EXPIRED",
            "GRACE_PERIOD",
            name="billingstatus",
        ),
        existing_type=sa.String(50),
        postgresql_using="billing_status::billingstatus",
    )

    op.alter_column(
        "organization_billing",
        "last_payment_status",
        type_=postgresql.ENUM("SUCCEEDED", "FAILED", "PENDING", name="paymentstatus"),
        existing_type=sa.String(50),
        postgresql_using="last_payment_status::paymentstatus",
        existing_nullable=True,
    )


def downgrade() -> None:
    # Convert enums back to strings
    op.alter_column(
        "organization_billing",
        "billing_plan",
        type_=sa.String(50),
        existing_type=postgresql.ENUM(
            "TRIAL", "DEVELOPER", "STARTUP", "ENTERPRISE", name="billingplan"
        ),
    )

    op.alter_column(
        "organization_billing",
        "billing_status",
        type_=sa.String(50),
        existing_type=postgresql.ENUM(
            "ACTIVE",
            "PAST_DUE",
            "CANCELED",
            "PAUSED",
            "TRIAL_EXPIRED",
            "GRACE_PERIOD",
            name="billingstatus",
        ),
    )

    op.alter_column(
        "organization_billing",
        "last_payment_status",
        type_=sa.String(50),
        existing_type=postgresql.ENUM("SUCCEEDED", "FAILED", "PENDING", name="paymentstatus"),
        existing_nullable=True,
    )

    # Drop the new columns if they exist
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'organization_billing'
            AND column_name IN ('grace_period_ends_at', 'payment_method_added', 'billing_metadata')
        """
        )
    )
    existing_columns = {row[0] for row in result}

    if "billing_metadata" in existing_columns:
        op.drop_column("organization_billing", "billing_metadata")
    if "payment_method_added" in existing_columns:
        op.drop_column("organization_billing", "payment_method_added")
    if "grace_period_ends_at" in existing_columns:
        op.drop_column("organization_billing", "grace_period_ends_at")

    # Drop enum types
    billing_plan_enum = postgresql.ENUM(
        "TRIAL", "DEVELOPER", "STARTUP", "ENTERPRISE", name="billingplan"
    )
    billing_plan_enum.drop(op.get_bind(), checkfirst=True)

    billing_status_enum = postgresql.ENUM(
        "ACTIVE",
        "PAST_DUE",
        "CANCELED",
        "PAUSED",
        "TRIAL_EXPIRED",
        "GRACE_PERIOD",
        name="billingstatus",
    )
    billing_status_enum.drop(op.get_bind(), checkfirst=True)

    payment_status_enum = postgresql.ENUM("SUCCEEDED", "FAILED", "PENDING", name="paymentstatus")
    payment_status_enum.drop(op.get_bind(), checkfirst=True)
