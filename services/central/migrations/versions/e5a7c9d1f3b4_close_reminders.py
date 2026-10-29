"""close reminders and escalation (spec v4 WP9, approval A1)

Revision ID: e5a7c9d1f3b4
Revises: d4f6b8c0e2a3
Create Date: 2026-10-30 10:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5a7c9d1f3b4"
down_revision: Union[str, None] = "d4f6b8c0e2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("referrals", sa.Column("close_reminder_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("referrals", sa.Column("reminders_sent", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("referrals", sa.Column("last_reminder_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("referrals", sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_referrals_close_reminder_due_at"), "referrals", ["close_reminder_due_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_referrals_close_reminder_due_at"), table_name="referrals")
    op.drop_column("referrals", "escalated_at")
    op.drop_column("referrals", "last_reminder_at")
    op.drop_column("referrals", "reminders_sent")
    op.drop_column("referrals", "close_reminder_due_at")
