"""add_bio_to_users

Revision ID: f386dfb7240d
Revises: 5dca4a9b3fe3
Create Date: 2025-12-11 16:23:08.320921

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f386dfb7240d'
down_revision = '5dca4a9b3fe3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add bio column to users table
    op.add_column('users', sa.Column('bio', sa.String(length=500), nullable=True))


def downgrade() -> None:
    # Remove bio column from users table
    op.drop_column('users', 'bio')
