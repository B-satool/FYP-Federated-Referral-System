"""end-to-end keys: key store, doctors' signed keys, group-key wraps, seen assertions (spec v4 WP1, approval A1)

Revision ID: b2d4f6a8c0e1
Revises: eb77d5fffde7
Create Date: 2026-10-29 18:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2d4f6a8c0e1"
down_revision: Union[str, None] = "eb77d5fffde7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "key_store",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purpose", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("public_spki", sa.Text(), nullable=False),
        sa.Column("private_sealed", sa.JSON(), nullable=False),
        sa.Column("entry", sa.JSON(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("purpose", "version"),
    )
    op.create_index("ix_key_store_purpose", "key_store", ["purpose"])
    op.create_table(
        "doctor_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("department", sa.String(length=60), nullable=True),
        sa.Column("enc_key_id", sa.String(length=16), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("entry", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("recovery", sa.Boolean(), nullable=False),
        sa.Column("approved_by", sa.String(length=200), nullable=True),
        sa.Column("revocation", sa.JSON(), nullable=True),
        sa.Column("revoked_by", sa.String(length=200), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for col in ("subject_id", "department", "enc_key_id", "status"):
        op.create_index(f"ix_doctor_keys_{col}", "doctor_keys", [col])
    op.create_table(
        "group_key_wraps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("department", sa.String(length=60), nullable=False),
        sa.Column("group_version", sa.Integer(), nullable=False),
        sa.Column("member_subject_id", sa.String(length=64), nullable=False),
        sa.Column("member_key_id", sa.String(length=16), nullable=False),
        sa.Column("wrapped", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("department", "group_version", "member_key_id"),
    )
    op.create_index("ix_group_key_wraps_department", "group_key_wraps", ["department"])
    op.create_index("ix_group_key_wraps_member_subject_id", "group_key_wraps", ["member_subject_id"])
    op.create_table(
        "seen_assertions",
        sa.Column("jti", sa.String(length=80), primary_key=True),
        sa.Column("issuer", sa.String(length=50), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_seen_assertions_expires_at", "seen_assertions", ["expires_at"])


def downgrade() -> None:
    op.drop_table("seen_assertions")
    op.drop_table("group_key_wraps")
    op.drop_table("doctor_keys")
    op.drop_table("key_store")
