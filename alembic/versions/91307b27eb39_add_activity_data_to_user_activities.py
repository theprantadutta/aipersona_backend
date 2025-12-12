"""add_activity_data_to_user_activities

Revision ID: 91307b27eb39
Revises: ffe068bb8411
Create Date: 2025-12-12 13:18:32.531175

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '91307b27eb39'
down_revision = 'ffe068bb8411'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename metadata column to activity_data in user_activities table
    op.alter_column('user_activities', 'metadata', new_column_name='activity_data')


def downgrade() -> None:
    # Rename activity_data column back to metadata
    op.alter_column('user_activities', 'activity_data', new_column_name='metadata')
