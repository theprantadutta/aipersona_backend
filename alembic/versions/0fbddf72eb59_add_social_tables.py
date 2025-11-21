"""add_social_tables

Revision ID: 0fbddf72eb59
Revises: ef100ba4a28f
Create Date: 2025-11-21 16:06:25.869092

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '0fbddf72eb59'
down_revision = 'ef100ba4a28f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create persona_likes table
    op.create_table(
        'persona_likes',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('persona_id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'persona_id', name='uq_user_persona_like')
    )
    op.create_index('idx_persona_likes_user', 'persona_likes', ['user_id'])
    op.create_index('idx_persona_likes_persona', 'persona_likes', ['persona_id'])

    # Create persona_favorites table
    op.create_table(
        'persona_favorites',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('persona_id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'persona_id', name='uq_user_persona_favorite')
    )
    op.create_index('idx_persona_favorites_user', 'persona_favorites', ['user_id'])
    op.create_index('idx_persona_favorites_persona', 'persona_favorites', ['persona_id'])

    # Create user_follows table
    op.create_table(
        'user_follows',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('follower_id', UUID(as_uuid=True), nullable=False),
        sa.Column('following_id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['follower_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['following_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('follower_id', 'following_id', name='uq_follower_following')
    )
    op.create_index('idx_user_follows_follower', 'user_follows', ['follower_id'])
    op.create_index('idx_user_follows_following', 'user_follows', ['following_id'])

    # Create persona_views table
    op.create_table(
        'persona_views',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('persona_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('viewed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['persona_id'], ['personas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_persona_views_persona', 'persona_views', ['persona_id'])
    op.create_index('idx_persona_views_user', 'persona_views', ['user_id'])
    op.create_index('idx_persona_views_date', 'persona_views', ['viewed_at'])


def downgrade() -> None:
    op.drop_index('idx_persona_views_date', 'persona_views')
    op.drop_index('idx_persona_views_user', 'persona_views')
    op.drop_index('idx_persona_views_persona', 'persona_views')
    op.drop_table('persona_views')

    op.drop_index('idx_user_follows_following', 'user_follows')
    op.drop_index('idx_user_follows_follower', 'user_follows')
    op.drop_table('user_follows')

    op.drop_index('idx_persona_favorites_persona', 'persona_favorites')
    op.drop_index('idx_persona_favorites_user', 'persona_favorites')
    op.drop_table('persona_favorites')

    op.drop_index('idx_persona_likes_persona', 'persona_likes')
    op.drop_index('idx_persona_likes_user', 'persona_likes')
    op.drop_table('persona_likes')
