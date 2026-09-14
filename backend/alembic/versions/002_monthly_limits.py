"""monthly token limits and system settings

Revision ID: 002_monthly_limits
Revises: 001_initial
Create Date: 2026-09-14 00:00:00.000000

Changes:
- users.daily_token_limit  -> users.monthly_token_limit
- users.daily_message_limit -> users.monthly_message_limit
- usage.date (YYYY-MM-DD)  -> usage.period (YYYY-MM), existing daily rows are
  dropped because limits are enforced per calendar month.
- new table system_settings (key/value store managed via the admin panel).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_monthly_limits'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('users', 'daily_token_limit', new_column_name='monthly_token_limit')
    op.alter_column('users', 'daily_message_limit', new_column_name='monthly_message_limit')

    op.execute('DELETE FROM usage')

    with op.batch_alter_table('usage') as batch:
        batch.alter_column('date', new_column_name='period', type_=sa.String(length=7))
        batch.create_unique_constraint('usage_user_id_period_key', ['user_id', 'period'])

    op.create_table(
        'system_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('system_settings')

    with op.batch_alter_table('usage') as batch:
        batch.drop_constraint('usage_user_id_period_key', type_='unique')
        batch.alter_column('period', new_column_name='date', type_=sa.String(length=10))

    op.alter_column('users', 'monthly_token_limit', new_column_name='daily_token_limit')
    op.alter_column('users', 'monthly_message_limit', new_column_name='daily_message_limit')