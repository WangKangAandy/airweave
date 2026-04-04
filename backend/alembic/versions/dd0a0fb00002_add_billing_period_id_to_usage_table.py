"""add_billing_period_id_to_usage_table

Revision ID: dd0a0fb00002
Revises: 7875ba8ce0f8
Create Date: 2025-07-26 13:17:02.914734

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'dd0a0fb00002'
down_revision = '7875ba8ce0f8'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the index that uses end_period column before dropping the column
    op.drop_index('ix_usage_organization_id_end_period', table_name='usage')

    # Drop columns that are no longer in the model
    op.drop_column('usage', 'start_period')
    op.drop_column('usage', 'end_period')

    # Add billing_period_id column to usage table
    op.add_column('usage',
        sa.Column('billing_period_id',
                  postgresql.UUID(as_uuid=True),
                  nullable=True)
    )

    # Create foreign key constraint
    op.create_foreign_key(
        'fk_usage_billing_period_id',
        'usage',
        'billing_period',
        ['billing_period_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Create unique constraint
    op.create_unique_constraint(
        'uq_usage_billing_period_id',
        'usage',
        ['billing_period_id']
    )

    # Create index
    op.create_index(
        'ix_usage_billing_period_id',
        'usage',
        ['billing_period_id']
    )


def downgrade():
    # Drop index
    op.drop_index('ix_usage_billing_period_id', table_name='usage')

    # Drop unique constraint
    op.drop_constraint('uq_usage_billing_period_id', 'usage', type_='unique')

    # Drop foreign key constraint
    op.drop_constraint('fk_usage_billing_period_id', 'usage', type_='foreignkey')

    # Drop column
    op.drop_column('usage', 'billing_period_id')

    # Re-add the old columns
    op.add_column('usage',
        sa.Column('start_period', sa.DATE(), nullable=False, server_default=sa.text("CURRENT_DATE"))
    )
    op.add_column('usage',
        sa.Column('end_period', sa.DATE(), nullable=False, server_default=sa.text("CURRENT_DATE"))
    )

    # Re-create the index
    op.create_index(
        'ix_usage_organization_id_end_period',
        'usage',
        ['organization_id', 'end_period']
    )
