"""consent, records requests and encrypted referral content (spec v4 WP2/WP3, approvals A1, A3 and A4)

Revision ID: d4f6b8c0e2a3
Revises: c3e5a7b9d1f2
Create Date: 2026-10-29 20:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4f6b8c0e2a3"
down_revision: Union[str, None] = "c3e5a7b9d1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(length=30), nullable=False, unique=True),
        sa.Column("referral_id", sa.Integer(), sa.ForeignKey("referrals.id"), nullable=False),
        sa.Column("patient_cnic", sa.String(length=15), nullable=False),
        sa.Column("patient_name", sa.String(length=200), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("requesting_org", sa.String(length=50), nullable=False),
        sa.Column("requesting_practitioner_id", sa.String(length=64), nullable=True),
        sa.Column("requesting_practitioner_name", sa.String(length=200), nullable=False),
        sa.Column("destination_org", sa.String(length=50), nullable=True),
        sa.Column("custodians_requested", sa.JSON(), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("sensitive_offered", sa.JSON(), nullable=False),
        sa.Column("data_period_start", sa.String(length=20), nullable=True),
        sa.Column("requested_by_id", sa.String(length=64), nullable=False),
        sa.Column("requested_by_name", sa.String(length=200), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("custodians_granted", sa.JSON(), nullable=False),
        sa.Column("sensitive_specific", sa.JSON(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document", sa.JSON(), nullable=True),
        sa.Column("patient_key_id", sa.String(length=16), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("revocation", sa.JSON(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_consents_referral_id", "consents", ["referral_id"])
    op.create_index("ix_consents_patient_cnic", "consents", ["patient_cnic"])
    op.create_index("ix_consents_status", "consents", ["status"])
    op.create_table(
        "record_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referral_id", sa.Integer(), sa.ForeignKey("referrals.id"), nullable=False),
        sa.Column("consent_id", sa.Integer(), sa.ForeignKey("consents.id"), nullable=False),
        sa.Column("custodian", sa.String(length=50), nullable=False),
        sa.Column("request_key", sa.String(length=200), nullable=False, unique=True),
        sa.Column("local_patient_id", sa.String(length=50), nullable=True),
        sa.Column("practitioner_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("refusals", sa.JSON(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(length=60), nullable=True),
        sa.Column("policy_version", sa.String(length=60), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(length=200), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_record_requests_referral_id", "record_requests", ["referral_id"])
    op.create_index("ix_record_requests_consent_id", "record_requests", ["consent_id"])
    op.create_index("ix_record_requests_status", "record_requests", ["status"])
    op.create_table(
        "encrypted_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referral_id", sa.Integer(), sa.ForeignKey("referrals.id"), nullable=False),
        sa.Column("batch_id", sa.String(length=60), nullable=False, unique=True),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("source_institution", sa.String(length=50), nullable=True),
        sa.Column("record_request_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_encrypted_batches_referral_id", "encrypted_batches", ["referral_id"])
    op.create_table(
        "encrypted_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referral_id", sa.Integer(), sa.ForeignKey("referrals.id"), nullable=False),
        sa.Column("batch_id", sa.String(length=60), nullable=False),
        sa.Column("item_id", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=True),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("item_date", sa.String(length=30), nullable=True),
        sa.Column("source_institution", sa.String(length=50), nullable=True),
        sa.Column("sensitive", sa.Boolean(), nullable=False),
        sa.Column("sealed", sa.JSON(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("ciphertext_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("batch_id", "item_id"),
    )
    op.create_index("ix_encrypted_items_referral_id", "encrypted_items", ["referral_id"])
    op.create_index("ix_encrypted_items_batch_id", "encrypted_items", ["batch_id"])
    op.create_table(
        "wrapped_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referral_id", sa.Integer(), sa.ForeignKey("referrals.id"), nullable=False),
        sa.Column("batch_id", sa.String(length=60), nullable=False),
        sa.Column("recipient_type", sa.String(length=20), nullable=False),
        sa.Column("recipient_subject", sa.String(length=100), nullable=False),
        sa.Column("recipient_key_id", sa.String(length=16), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=True),
        sa.Column("wrapped", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("batch_id", "recipient_key_id"),
    )
    for col in ("referral_id", "batch_id", "recipient_subject", "recipient_key_id"):
        op.create_index(f"ix_wrapped_keys_{col}", "wrapped_keys", [col])
    op.create_table(
        "package_manifests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referral_id", sa.Integer(), sa.ForeignKey("referrals.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("signer_subject", sa.String(length=64), nullable=False),
        sa.Column("signer_key_id", sa.String(length=16), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("superseded", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("referral_id", "version"),
    )
    op.create_index("ix_package_manifests_referral_id", "package_manifests", ["referral_id"])
    op.create_table(
        "purge_receipts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referral_id", sa.Integer(), sa.ForeignKey("referrals.id"), nullable=False, unique=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("items_count", sa.Integer(), nullable=False),
        sa.Column("wrapped_keys_count", sa.Integer(), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=True),
        sa.Column("trigger", sa.String(length=40), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    for t in ("purge_receipts", "package_manifests", "wrapped_keys", "encrypted_items", "encrypted_batches",
              "record_requests", "consents"):
        op.drop_table(t)
