"""add usage table for organization subscription tracking

Revision ID: 3c0d6c431e21
Revises: 520c9ab65c5f
Create Date: 2025-07-24 14:00:09.027251

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c0d6c431e21'
down_revision = '520c9ab65c5f'
branch_labels = None
depends_on = None


def upgrade():
    # Create usage table following standard OrganizationBase pattern with monthly tracking
    op.create_table(
        'usage',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('start_period', sa.Date(), nullable=False),
        sa.Column('end_period', sa.Date(), nullable=False),
        sa.Column('syncs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('entities', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('queries', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('collections', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('source_connections', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('modified_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['organization_id'],
            ['organization.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create index on organization_id for fast lookups (not unique since we have multiple rows per org)
    op.create_index(
        op.f('ix_usage_organization_id'),
        'usage',
        ['organization_id'],
        unique=False
    )

    # Create composite index for efficient querying of most recent period
    op.create_index(
        'ix_usage_organization_id_end_period',
        'usage',
        ['organization_id', 'end_period'],
        unique=False
    )


def downgrade():
    # Drop indexes first
    op.drop_index('ix_usage_organization_id_end_period', table_name='usage')
    op.drop_index(op.f('ix_usage_organization_id'), table_name='usage')

    # Drop table
    op.drop_table('usage')
