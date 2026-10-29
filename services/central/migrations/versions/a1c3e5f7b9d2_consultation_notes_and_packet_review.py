"""consultation notes and the doctor's packet review

Revision ID: a1c3e5f7b9d2
Revises: fec095fdc2b0
Create Date: 2026-10-29 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1c3e5f7b9d2"
down_revision: Union[str, None] = "fec095fdc2b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("referrals", sa.Column("consultation_notes", sa.Text(), nullable=False, server_default=""))
    op.add_column("referrals", sa.Column("packet_reviewed_by", sa.String(length=200), nullable=True))
    op.add_column("referrals", sa.Column("packet_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("drug_interactions", sa.Column("label_quote", sa.Text(), nullable=True))
    op.add_column("drug_interactions", sa.Column("label_source", sa.String(length=200), nullable=True))
    op.add_column("drug_interactions", sa.Column("label_section", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("drug_interactions", "label_section")
    op.drop_column("drug_interactions", "label_source")
    op.drop_column("drug_interactions", "label_quote")
    op.drop_column("referrals", "packet_reviewed_at")
    op.drop_column("referrals", "packet_reviewed_by")
    op.drop_column("referrals", "consultation_notes")
