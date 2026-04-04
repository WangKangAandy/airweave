"""fix_api_key_table_for_encryption

Revision ID: 965a6588169d
Revises: 6f85e990edd4
Create Date: 2025-05-12 11:41:53.407023

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '965a6588169d'
down_revision = '6f85e990edd4'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the unique constraint first
    op.drop_constraint('api_key_key_key', 'api_key', type_='unique')

    # Rename key column to encrypted_key
    op.alter_column('api_key', 'key', new_column_name='encrypted_key')

    # Create a new unique constraint for encrypted_key
    op.create_unique_constraint('api_key_encrypted_key_key', 'api_key', ['encrypted_key'])

    # Drop key_prefix column
    op.drop_column('api_key', 'key_prefix')


def downgrade():
    # Add back key_prefix column
    op.add_column('api_key', sa.Column('key_prefix', sa.String(8), nullable=False,
                                      server_default='00000000'))

    # Drop unique constraint on encrypted_key
    op.drop_constraint('api_key_encrypted_key_key', 'api_key', type_='unique')

    # Rename encrypted_key back to key
    op.alter_column('api_key', 'encrypted_key', new_column_name='key')

    # Recreate the original constraint
    op.create_unique_constraint('api_key_key_key', 'api_key', ['key'])

    # Remove server default on key_prefix
    op.alter_column('api_key', 'key_prefix', server_default=None)
