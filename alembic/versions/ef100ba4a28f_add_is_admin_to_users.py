"""add_is_admin_to_users

Revision ID: ef100ba4a28f
Revises: 4f3ba62d9294
Create Date: 2025-11-21 14:15:53.437310

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ef100ba4a28f'
down_revision = '4f3ba62d9294'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_admin column to users table
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove is_admin column from users table
    op.drop_column('users', 'is_admin')
