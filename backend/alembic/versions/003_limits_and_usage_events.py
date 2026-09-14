"""user limit states and usage events ledger

Revision ID: 003_limits_and_usage_events
Revises: 002_monthly_limits
Create Date: 2026-09-14 00:00:00.000000

Changes:
- users.limits_exempt (bool, default false)
- users.custom_monthly_token_limit (int, nullable)
- users.unlimited (bool, default false)

  Existing users therefore get the safe default:
      limits_exempt            = false
      custom_monthly_token_limit = NULL
      unlimited                = false
  and continue to use the configured global standard limit.

- new table usage_events (the granular usage ledger per action):
    id, user_id, action_type, tokens, period (YYYY-MM), metadata, created_at

Note: the global default limit / action costs (chat_message_cost,
image_generation_cost) live in system_settings and are seeded by
bootstrap_settings on startup. Existing configured values are never
overwritten.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_limits_and_usage_events'
down_revision = '002_monthly_limits'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('limits_exempt', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.add_column(
        'users',
        sa.Column('custom_monthly_token_limit', sa.Integer(), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column('unlimited', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )

    op.create_table(
        'usage_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('tokens', sa.Integer(), nullable=False),
        sa.Column('period', sa.String(length=7), nullable=False),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_usage_events_user_id', 'usage_events', ['user_id'])
    op.create_index('ix_usage_events_period', 'usage_events', ['period'])
    op.create_index('ix_usage_events_action_type', 'usage_events', ['action_type'])


def downgrade() -> None:
    op.drop_index('ix_usage_events_action_type', table_name='usage_events')
    op.drop_index('ix_usage_events_period', table_name='usage_events')
    op.drop_index('ix_usage_events_user_id', table_name='usage_events')
    op.drop_table('usage_events')

    op.drop_column('users', 'unlimited')
    op.drop_column('users', 'custom_monthly_token_limit')
    op.drop_column('users', 'limits_exempt')