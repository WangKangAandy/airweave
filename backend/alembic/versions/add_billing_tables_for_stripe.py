"""Add billing tables for stripe integration

Revision ID: add_billing_tables
Revises: 520c9ab65c5f
Create Date: 2024-01-29 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "add_billing_tables"
down_revision = "520c9ab65c5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create organization_billing table
    op.create_table(
        "organization_billing",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("billing_plan", sa.String(length=50), nullable=False),
        sa.Column("billing_status", sa.String(length=50), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
        sa.Column("billing_email", sa.String(length=255), nullable=False),
        sa.Column("payment_method_id", sa.String(length=255), nullable=True),
        sa.Column("last_payment_status", sa.String(length=50), nullable=True),
        sa.Column("last_payment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
        sa.UniqueConstraint("stripe_customer_id"),
        sa.UniqueConstraint("stripe_subscription_id"),
    )

    # Create indexes for billing table
    op.create_index(
        "idx_org_billing_stripe_customer", "organization_billing", ["stripe_customer_id"]
    )
    op.create_index(
        "idx_org_billing_stripe_subscription", "organization_billing", ["stripe_subscription_id"]
    )

    # Create billing_event table
    op.create_table(
        "billing_event",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("stripe_event_id", sa.String(length=255), nullable=True),
        sa.Column("event_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_event_id"),
    )

    # Create indexes for billing_event table
    op.create_index("idx_billing_events_org", "billing_event", ["organization_id"])
    op.create_index("idx_billing_events_type", "billing_event", ["event_type"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_billing_events_type", "billing_event")
    op.drop_index("idx_billing_events_org", "billing_event")
    op.drop_index("idx_org_billing_stripe_subscription", "organization_billing")
    op.drop_index("idx_org_billing_stripe_customer", "organization_billing")

    # Drop tables
    op.drop_table("billing_event")
    op.drop_table("organization_billing")
