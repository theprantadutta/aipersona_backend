"""add_blocking_reporting_activity_tables

Revision ID: ffe068bb8411
Revises: f386dfb7240d
Create Date: 2025-12-11 16:38:51.317389

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ffe068bb8411'
down_revision = 'f386dfb7240d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_blocks table
    op.create_table(
        'user_blocks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('blocker_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('blocked_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(['blocker_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['blocked_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('blocker_id', 'blocked_id', name='uq_blocker_blocked')
    )
    op.create_index('idx_user_blocks_blocker', 'user_blocks', ['blocker_id'], unique=False)
    op.create_index('idx_user_blocks_blocked', 'user_blocks', ['blocked_id'], unique=False)

    # Create content_reports table
    op.create_table(
        'content_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reporter_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_id', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(50), nullable=False),
        sa.Column('reason', sa.String(50), nullable=False),
        sa.Column('additional_info', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), server_default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['reporter_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_content_reports_reporter', 'content_reports', ['reporter_id'], unique=False)
    op.create_index('idx_content_reports_content', 'content_reports', ['content_id'], unique=False)
    op.create_index('idx_content_reports_status', 'content_reports', ['status'], unique=False)
    op.create_index('idx_content_reports_type', 'content_reports', ['content_type'], unique=False)
    op.create_index('idx_content_reports_created', 'content_reports', ['created_at'], unique=False)

    # Create user_activities table
    op.create_table(
        'user_activities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('activity_type', sa.String(50), nullable=False),
        sa.Column('target_id', sa.String(255), nullable=True),
        sa.Column('target_type', sa.String(50), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_user_activities_user', 'user_activities', ['user_id'], unique=False)
    op.create_index('idx_user_activities_type', 'user_activities', ['activity_type'], unique=False)
    op.create_index('idx_user_activities_created', 'user_activities', ['created_at'], unique=False)
    op.create_index('idx_user_activities_target', 'user_activities', ['target_id'], unique=False)


def downgrade() -> None:
    # Drop user_activities table
    op.drop_index('idx_user_activities_target', table_name='user_activities')
    op.drop_index('idx_user_activities_created', table_name='user_activities')
    op.drop_index('idx_user_activities_type', table_name='user_activities')
    op.drop_index('idx_user_activities_user', table_name='user_activities')
    op.drop_table('user_activities')

    # Drop content_reports table
    op.drop_index('idx_content_reports_created', table_name='content_reports')
    op.drop_index('idx_content_reports_type', table_name='content_reports')
    op.drop_index('idx_content_reports_status', table_name='content_reports')
    op.drop_index('idx_content_reports_content', table_name='content_reports')
    op.drop_index('idx_content_reports_reporter', table_name='content_reports')
    op.drop_table('content_reports')

    # Drop user_blocks table
    op.drop_index('idx_user_blocks_blocked', table_name='user_blocks')
    op.drop_index('idx_user_blocks_blocker', table_name='user_blocks')
    op.drop_table('user_blocks')
