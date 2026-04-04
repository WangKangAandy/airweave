"""Convert datetime columns to timezone naive

Revision ID: 01538fc19202
Revises: 16b5ba5572fb
Create Date: 2025-01-26 14:40:17.745436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '01538fc19202'
down_revision: Union[str, None] = '16b5ba5572fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert DateTime columns to timezone-naive (TIMESTAMP WITHOUT TIME ZONE)

    # api_key table
    op.alter_column('api_key', 'expiration_date',
                    type_=sa.DateTime(timezone=False),
                    postgresql_using='expiration_date AT TIME ZONE \'UTC\'',
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False)

    # billing_period table
    op.alter_column('billing_period', 'period_start',
                    type_=sa.DateTime(timezone=False),
                    postgresql_using='period_start AT TIME ZONE \'UTC\'',
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False)

    op.alter_column('billing_period', 'period_end',
                    type_=sa.DateTime(timezone=False),
                    postgresql_using='period_end AT TIME ZONE \'UTC\'',
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=False)

    op.alter_column('billing_period', 'paid_at',
                    type_=sa.DateTime(timezone=False),
                    postgresql_using='paid_at AT TIME ZONE \'UTC\'',
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)

    # organization_billing table
    op.alter_column('organization_billing', 'trial_ends_at',
                    type_=sa.DateTime(timezone=False),
                    postgresql_using='trial_ends_at AT TIME ZONE \'UTC\'',
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)

    op.alter_column('organization_billing', 'grace_period_ends_at',
                    type_=sa.DateTime(timezone=False),
                    postgresql_using='grace_period_ends_at AT TIME ZONE \'UTC\'',
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)

    op.alter_column('organization_billing', 'current_period_start',
                    type_=sa.DateTime(timezone=False),
                    postgresql_using='current_period_start AT TIME ZONE \'UTC\'',
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)

    op.alter_column('organization_billing', 'current_period_end',
                    type_=sa.DateTime(timezone=False),
                    postgresql_using='current_period_end AT TIME ZONE \'UTC\'',
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)

    op.alter_column('organization_billing', 'pending_plan_change_at',
                    type_=sa.DateTime(timezone=False),
                    postgresql_using='pending_plan_change_at AT TIME ZONE \'UTC\'',
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)

    op.alter_column('organization_billing', 'last_payment_at',
                    type_=sa.DateTime(timezone=False),
                    postgresql_using='last_payment_at AT TIME ZONE \'UTC\'',
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)

    # sync table
    op.alter_column('sync', 'next_scheduled_run',
                    type_=sa.DateTime(timezone=False),
                    postgresql_using='next_scheduled_run AT TIME ZONE \'UTC\'',
                    existing_type=sa.DateTime(timezone=True),
                    existing_nullable=True)


def downgrade() -> None:
    # Convert DateTime columns back to timezone-aware (TIMESTAMP WITH TIME ZONE)

    # sync table
    op.alter_column('sync', 'next_scheduled_run',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(timezone=False),
                    existing_nullable=True)

    # organization_billing table
    op.alter_column('organization_billing', 'last_payment_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(timezone=False),
                    existing_nullable=True)

    op.alter_column('organization_billing', 'pending_plan_change_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(timezone=False),
                    existing_nullable=True)

    op.alter_column('organization_billing', 'current_period_end',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(timezone=False),
                    existing_nullable=True)

    op.alter_column('organization_billing', 'current_period_start',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(timezone=False),
                    existing_nullable=True)

    op.alter_column('organization_billing', 'grace_period_ends_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(timezone=False),
                    existing_nullable=True)

    op.alter_column('organization_billing', 'trial_ends_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(timezone=False),
                    existing_nullable=True)

    # billing_period table
    op.alter_column('billing_period', 'paid_at',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(timezone=False),
                    existing_nullable=True)

    op.alter_column('billing_period', 'period_end',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(timezone=False),
                    existing_nullable=False)

    op.alter_column('billing_period', 'period_start',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(timezone=False),
                    existing_nullable=False)

    # api_key table
    op.alter_column('api_key', 'expiration_date',
                    type_=sa.DateTime(timezone=True),
                    existing_type=sa.DateTime(timezone=False),
                    existing_nullable=False)
