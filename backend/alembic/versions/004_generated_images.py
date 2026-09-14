"""generated images table and message image linkage

Revision ID: 004_generated_images
Revises: 003_limits_and_usage_events
Create Date: 2026-09-14 00:00:00.000000

Changes:
- new table generated_images (one row per generated image):
    id, user_id, chat_id (nullable), prompt, provider, model, status,
    image_path, width, height, bytes_size, seconds, token_cost, period,
    error, created_at

- messages.image_id (nullable FK set-null) links an assistant chat message
  to the generated image it displays.

Every image is permanently assigned to the owning user (user_id FK CASCADE)
and - when generated inside a chat - to that chat (chat_id FK CASCADE). The
image bytes live on disk under the media volume; the database only stores the
path and the generation metadata.

Existing data is untouched; the new columns are nullable/defaulted.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_generated_images'
down_revision = '003_limits_and_usage_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'generated_images',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.Integer(), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('provider', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'done'")),
        sa.Column('image_path', sa.String(length=500), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('bytes_size', sa.Integer(), nullable=True),
        sa.Column('seconds', sa.Float(), nullable=True),
        sa.Column('token_cost', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('period', sa.String(length=7), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_generated_images_user_id', 'generated_images', ['user_id'])
    op.create_index('ix_generated_images_chat_id', 'generated_images', ['chat_id'])

    op.add_column(
        'messages',
        sa.Column('image_id', sa.Integer(), nullable=True),
    )
    op.create_index('ix_messages_image_id', 'messages', ['image_id'])
    op.create_foreign_key(
        'fk_messages_image_id_generated_images',
        'messages',
        'generated_images',
        ['image_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_messages_image_id_generated_images', 'messages', type_='foreignkey')
    op.drop_index('ix_messages_image_id', table_name='messages')
    op.drop_column('messages', 'image_id')

    op.drop_index('ix_generated_images_chat_id', table_name='generated_images')
    op.drop_index('ix_generated_images_user_id', table_name='generated_images')
    op.drop_table('generated_images')