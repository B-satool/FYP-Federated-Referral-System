"""records requests under consent and policy; sensitive-category markers (spec v4 WP2, approvals A1 and A3)

Revision ID: c4e6a8b0d2f3
Revises: b2d4f6a8c0e1
Create Date: 2026-10-29 20:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4e6a8b0d2f3"
down_revision: Union[str, None] = "b2d4f6a8c0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RECORD_TABLES = ("conditions", "visits", "medications", "lab_results", "imaging_reports")


def upgrade() -> None:
    for table in RECORD_TABLES:
        op.add_column(table, sa.Column("sensitive_category", sa.String(length=40), nullable=True))
    op.create_table(
        "record_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_key", sa.String(length=200), nullable=False, unique=True),
        sa.Column("referral_ref", sa.String(length=40), nullable=False),
        sa.Column("requesting_org", sa.String(length=50), nullable=False),
        sa.Column("practitioner_id", sa.String(length=64), nullable=False),
        sa.Column("practitioner_name", sa.String(length=200), nullable=True),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("consent_ref", sa.String(length=60), nullable=False),
        sa.Column("local_patient_id", sa.String(length=50), nullable=True),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("since", sa.String(length=20), nullable=True),
        sa.Column("reason_text", sa.Text(), nullable=True),
        sa.Column("sensitive", sa.JSON(), nullable=False),
        sa.Column("practitioner_entry", sa.JSON(), nullable=True),
        sa.Column("patient_entry", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("refusals", sa.JSON(), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("decided_by", sa.String(length=200), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_record_requests_referral_ref", "record_requests", ["referral_ref"])
    op.create_index("ix_record_requests_status", "record_requests", ["status"])


def downgrade() -> None:
    op.drop_table("record_requests")
    for table in RECORD_TABLES:
        op.drop_column(table, "sensitive_category")
