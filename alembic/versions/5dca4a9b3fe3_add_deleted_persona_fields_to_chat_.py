"""add_deleted_persona_fields_to_chat_sessions

Revision ID: 5dca4a9b3fe3
Revises: 0fbddf72eb59
Create Date: 2025-11-29 14:53:27.512396

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5dca4a9b3fe3'
down_revision = '0fbddf72eb59'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns for deleted persona tracking
    op.add_column('chat_sessions', sa.Column('deleted_persona_name', sa.String(255), nullable=True))
    op.add_column('chat_sessions', sa.Column('deleted_persona_image', sa.String(500), nullable=True))
    op.add_column('chat_sessions', sa.Column('persona_deleted_at', sa.DateTime(), nullable=True))

    # Make persona_id nullable
    op.alter_column('chat_sessions', 'persona_id', nullable=True)

    # Drop the old foreign key constraint and create new one with SET NULL
    op.drop_constraint('chat_sessions_persona_id_fkey', 'chat_sessions', type_='foreignkey')
    op.create_foreign_key(
        'chat_sessions_persona_id_fkey',
        'chat_sessions',
        'personas',
        ['persona_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Drop the SET NULL foreign key and recreate with CASCADE
    op.drop_constraint('chat_sessions_persona_id_fkey', 'chat_sessions', type_='foreignkey')
    op.create_foreign_key(
        'chat_sessions_persona_id_fkey',
        'chat_sessions',
        'personas',
        ['persona_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Make persona_id non-nullable again (will fail if any nulls exist)
    op.alter_column('chat_sessions', 'persona_id', nullable=False)

    # Remove the new columns
    op.drop_column('chat_sessions', 'persona_deleted_at')
    op.drop_column('chat_sessions', 'deleted_persona_image')
    op.drop_column('chat_sessions', 'deleted_persona_name')
