"""remove per-patient sharing grants: consent and this institution's policy replace them (spec v4 6.2, approval A3)

Revision ID: d5f7b9c1e3a4
Revises: c4e6a8b0d2f3
Create Date: 2026-10-29 21:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d5f7b9c1e3a4"
down_revision: Union[str, None] = "c4e6a8b0d2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("access_grants")


def downgrade() -> None:
    op.create_table(
        "access_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("grantee_institution", sa.String(length=50), nullable=False, index=True),
        sa.Column("local_patient_id", sa.String(length=50), nullable=False, index=True),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("granted_by", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_by", sa.String(length=200), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("referral_ref", sa.String(length=60), nullable=True, index=True),
    )
