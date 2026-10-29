"""end-to-end key directory, group-key wraps, platform key, seen assertions (spec v4 WP1, approval A1)

Revision ID: c3e5a7b9d1f2
Revises: a1c3e5f7b9d2
Create Date: 2026-10-29 18:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3e5a7b9d1f2"
down_revision: Union[str, None] = "a1c3e5f7b9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "key_directory",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject_id", sa.String(length=100), nullable=False),
        sa.Column("subject_type", sa.String(length=20), nullable=False),
        sa.Column("hospital_id", sa.String(length=50), nullable=True),
        sa.Column("department", sa.String(length=60), nullable=True),
        sa.Column("enc_key_id", sa.String(length=16), nullable=False, unique=True),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("issued_by", sa.String(length=50), nullable=False),
        sa.Column("entry", sa.JSON(), nullable=False),
        sa.Column("revocation", sa.JSON(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for col in ("subject_id", "subject_type", "hospital_id", "department"):
        op.create_index(f"ix_key_directory_{col}", "key_directory", [col])
    op.create_table(
        "group_key_wraps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hospital_id", sa.String(length=50), nullable=False),
        sa.Column("department", sa.String(length=60), nullable=False),
        sa.Column("group_version", sa.Integer(), nullable=False),
        sa.Column("member_subject_id", sa.String(length=64), nullable=False),
        sa.Column("member_key_id", sa.String(length=16), nullable=False),
        sa.Column("wrapped", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("hospital_id", "department", "group_version", "member_key_id"),
    )
    op.create_index("ix_group_key_wraps_member_subject_id", "group_key_wraps", ["member_subject_id"])
    op.create_index("ix_group_key_wraps_member_key_id", "group_key_wraps", ["member_key_id"])
    op.create_table(
        "platform_keys",
        sa.Column("kid", sa.String(length=16), primary_key=True),
        sa.Column("public_spki", sa.Text(), nullable=False),
        sa.Column("private_sealed", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "seen_assertions",
        sa.Column("jti", sa.String(length=80), primary_key=True),
        sa.Column("issuer", sa.String(length=50), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_seen_assertions_expires_at", "seen_assertions", ["expires_at"])


def downgrade() -> None:
    op.drop_table("seen_assertions")
    op.drop_table("platform_keys")
    op.drop_table("group_key_wraps")
    op.drop_table("key_directory")
