"""Package manifest, copy verification and the purged envelope (minimal central storage).

A sent package is immutable because its SHA-256 never changes. Once the working set is purged,
central keeps only a manifest (what the package contained, by source record and version, and the
flags and rule set) plus that hash. The clinical content is held by the sending clinic (its own
copy), the receiving institution (its record) and the sources (which keep every record version).
"""
from __future__ import annotations

from typing import Any

from refcommon.exchange import package_hash

PURGED_MARKER = "content removed: the temporary working set for this referral has ended"


def build_manifest(envelope: dict[str, Any]) -> dict[str, Any]:
    """Reference list of what the package contained. Holds no clinical values."""
    items = [{
        "evidence_id": e.get("evidence_id"), "category": e.get("category"), "origin": e.get("origin"),
        "source_institution": e.get("source_institution"), "source_record_type": e.get("source_record_type"),
        "source_record_id": e.get("source_record_id"), "source_record_version": e.get("source_record_version"),
    } for e in envelope.get("evidence", [])]
    flags = [{"flag_id": f.get("flag_id"), "version": f.get("version"), "kind": f.get("kind"),
              "rule_id": f.get("rule_id"), "rule_version": f.get("rule_version"), "source_type": f.get("source_type"),
              "source_ref": f.get("source_ref"), "decision": (f.get("acknowledged") or {}).get("decision")}
             for f in envelope.get("medication_flags", [])]
    evaluation = envelope.get("medication_evaluation") or {}
    return {
        "manifest_version": 1, "referral_id": envelope.get("referral_id"),
        "package_version": envelope.get("package_version"), "sender_institution": envelope.get("sender_institution"),
        "destination_institution": envelope.get("destination_institution"),
        "sent_by_id": envelope.get("sent_by_id"), "sent_at": str(envelope.get("sent_at")),
        "content_hash": envelope.get("content_hash"), "ruleset_hash": evaluation.get("ruleset_hash"),
        "evidence": items, "medication_flags": flags,
        "selection": envelope.get("selection"),  # who chose each item and what the AI recommended
        "ai_suggestions": [s.get("pair_key") for s in envelope.get("ai_suggestions", [])],
    }


def verify_copy(stored_hash: str, copy: dict[str, Any] | None) -> dict[str, str]:
    """Check a copy of the package (from the sender or the receiver) against the kept hash."""
    try:
        computed = package_hash(copy)  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001 - an unusable copy is a result, not a crash
        return {"result": "unusable_copy", "message": "The copy could not be checked"}
    if computed == stored_hash:
        return {"result": "match", "message": "The copy is identical to what was sent"}
    return {"result": "mismatch", "message": "The copy differs from what was sent"}


def purged_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    """What remains of an envelope after purge: identifiers and the hash, no clinical content."""
    keep = ("referral_id", "package_version", "sender_institution", "destination_institution", "content_hash",
            "delivery_key", "sent_by", "sent_by_id", "sent_at", "envelope_version")
    out = {k: envelope.get(k) for k in keep}
    out["purged"] = True
    out["note"] = PURGED_MARKER
    return out


def is_purged(envelope: dict[str, Any] | None) -> bool:
    return bool(envelope and envelope.get("purged"))
