"""audit hash chain and append-only trigger (spec v4 11.5, WP11)

Revision ID: f6b8d0e2a4c5
Revises: e5a7c9d1f3b4
Create Date: 2026-10-30 14:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f6b8d0e2a4c5"
down_revision: Union[str, None] = "e5a7c9d1f3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TRIGGER = """
CREATE OR REPLACE FUNCTION audit_events_append_only() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'audit_events is append-only';
  END IF;
  IF OLD.chain_hash IS NOT NULL THEN
    RAISE EXCEPTION 'a sealed audit event cannot change';
  END IF;
  IF (NEW.id, NEW.actor_id, NEW.actor_name, NEW.institution_id, NEW.action, NEW.target_type, NEW.target_id,
      NEW.referral_id, NEW.outcome, NEW.detail::text, NEW.created_at)
     IS DISTINCT FROM
     (OLD.id, OLD.actor_id, OLD.actor_name, OLD.institution_id, OLD.action, OLD.target_type, OLD.target_id,
      OLD.referral_id, OLD.outcome, OLD.detail::text, OLD.created_at) THEN
    RAISE EXCEPTION 'only the hash-chain columns of an audit event may be set';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION audit_events_append_only();
"""


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("chain_seq", sa.Integer(), nullable=True))
    op.add_column("audit_events", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("chain_hash", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_audit_events_chain_seq", "audit_events", ["chain_seq"])
    op.execute(TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS audit_events_append_only()")
    op.drop_constraint("uq_audit_events_chain_seq", "audit_events", type_="unique")
    op.drop_column("audit_events", "chain_hash")
    op.drop_column("audit_events", "prev_hash")
    op.drop_column("audit_events", "chain_seq")
