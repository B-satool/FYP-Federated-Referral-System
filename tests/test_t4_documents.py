"""T4 - documents, OCR and evidence review (FR-22 to FR-34, FR-37, FR-58)."""
from __future__ import annotations

from pathlib import Path

import httpx
from conftest import new_referral
from helpers import CENTRAL, central, ok, token, wait_for

SAMPLES = Path(__file__).resolve().parent.parent / "samples" / "documents"
DR, STAFF = "dr.malik", "staff.a"


def upload(ref_id: int, name: str, doc_type: str, content_type: str, user: str = STAFF) -> httpx.Response:
    with open(SAMPLES / name, "rb") as fh:
        return httpx.post(f"{CENTRAL}/referrals/{ref_id}/documents", headers={"Authorization": f"Bearer {token(user)}"},
                          files={"file": (name, fh, content_type)}, data={"doc_type": doc_type}, timeout=60)


def wait_job(job_id: str) -> dict:
    return wait_for(lambda: (j := ok(central(STAFF).get(f"/jobs/{job_id}")))["status"] in ("completed", "failed") and j,
                    timeout=120, interval=1.5, what=f"job {job_id}")


def test_digital_pdf_extraction_correction_verification_and_discrepancy():
    staff, dr = central(STAFF), central(DR)
    ref = new_referral("MR-102")
    rid = ref["id"]
    ok(dr.post(f"/referrals/{rid}/retrieve"))
    up = ok(upload(rid, "prescription_cardiology_digital.pdf", "prescription", "application/pdf"), 201)
    assert up["job"]["status"] == "queued"
    job = wait_job(up["job"]["id"])
    assert job["status"] == "completed", job
    doc = ok(staff.get(f"/documents/{up['document']['id']}"))
    assert doc["extraction"]["text_source"] == "embedded"
    fields = doc["fields"]
    warfarin = next(f for f in fields if f["category"] == "medication" and "Warfarin" in f["display"])
    assert warfarin["verification_status"] == "unverified" and warfarin["review_state"] == "proposed"  # FR-25
    assert warfarin["page"] == 1 and warfarin["source_text"] and "7.5" in warfarin["original"]["strength"]

    # original document retained and page image available through authenticated endpoints only
    assert httpx.get(f"{CENTRAL}/documents/{up['document']['id']}/file", headers={"Authorization": f"Bearer {token(STAFF)}"}).content.startswith(b"%PDF")
    assert httpx.get(f"{CENTRAL}/documents/{up['document']['id']}/pages/1", headers={"Authorization": f"Bearer {token(STAFF)}"}).status_code == 200
    assert httpx.get(f"{CENTRAL}/documents/{up['document']['id']}/file").status_code == 401
    assert httpx.get(f"{CENTRAL}/documents/{up['document']['id']}/file", headers={"Authorization": f"Bearer {token('staff.x')}"}).status_code == 403

    # dose differs from the Clinic A record -> supported discrepancy with both sources and dates (FR-37)
    items = ok(dr.get(f"/referrals/{rid}/review-items"))
    disc = next(i for i in items if i["kind"] == "discrepancy" and "warfarin" in i["title"].lower())
    assert "Clinic A" in disc["detail"] and "Uploaded document" in disc["detail"] and "2021-06-01" in disc["detail"]
    # different INR values on different dates are NOT a conflict (FR-38)
    assert not any(i["kind"] == "discrepancy" and "INR" in i["title"] for i in items)

    # correction keeps the prior extracted value; staff cannot verify, clinician can (FR-26, FR-28)
    corrected = ok(staff.post(f"/evidence/{warfarin['id']}/correct", {
        "fields": {"dosage_text": "7.5 mg orally once daily (per cardiology letter)"}, "note": "Matched to letter",
        "expected_row_version": warfarin["row_version"]}))
    assert corrected["review_state"] == "corrected"
    assert corrected["original"]["dosage_text"] != corrected["current"]["dosage_text"]
    assert staff.post(f"/evidence/{warfarin['id']}/verify", {"expected_row_version": corrected["row_version"]}).status_code == 403
    verified = ok(dr.post(f"/evidence/{warfarin['id']}/verify", {"expected_row_version": corrected["row_version"], "note": "Checked"}))
    assert verified["verification_status"] == "verified" and verified["verified_by"] == "Sana Malik"
    history = ok(dr.get(f"/evidence/{warfarin['id']}"))
    assert [r["action"] for r in history["revisions"]] == ["correct", "verify"]
    assert history["revisions"][0]["prior_value"]["dosage_text"] == warfarin["original"]["dosage_text"]

    # clinician resolves the discrepancy with a recorded rationale (FR-40)
    assert staff.post(f"/review-items/{disc['id']}/resolve", {"action": "resolved", "rationale": "x" * 10}).status_code == 403
    res = ok(dr.post(f"/review-items/{disc['id']}/resolve",
                     {"action": "resolved", "rationale": "Cardiology increased dose on 01/09/2026; 7.5 mg is current"}))
    assert res["status"] == "resolved" and res["resolved_by"] == "Sana Malik"


def test_scanned_image_ocr_unreadable_and_rejected_files():
    staff = central(STAFF)
    ref = new_referral("MR-102")
    rid = ref["id"]
    scan = ok(upload(rid, "referral_note_scan.jpg", "referral_note", "image/jpeg"), 201)
    job = wait_job(scan["job"]["id"])
    assert job["status"] == "completed"
    doc = ok(staff.get(f"/documents/{scan['document']['id']}"))
    assert doc["extraction"]["text_source"] == "ocr" and doc["extraction"]["ocr_engine"] == "tesseract"
    names = " ".join(f["display"] for f in doc["fields"])
    assert "Ecosprin" in names and "INR" in names
    inr = next(f for f in doc["fields"] if f["display"].startswith("INR"))
    assert inr["region"] and 0 <= inr["region"]["x"] <= 1 and inr["original"]["value"] == 2.6
    assert "not a clinical probability" in inr["confidence"]["note"]

    bad = ok(upload(rid, "unreadable_scan.png", "other", "image/png"), 201)
    job = wait_job(bad["job"]["id"])
    doc = ok(staff.get(f"/documents/{bad['document']['id']}"))
    assert doc["document"]["status"] == "unreadable" and not doc["fields"]
    assert "manually" in doc["document"]["error"]

    rejected = upload(rid, "rejected_not_a_pdf.pdf", "prescription", "application/pdf")
    assert rejected.status_code == 415 and rejected.json()["detail"]["code"] == "unsupported_type"
    docs = ok(staff.get(f"/referrals/{rid}/documents"))
    assert all(d["original_filename"] != "rejected_not_a_pdf.pdf" for d in docs)


def test_manual_transcription_without_ocr_and_unresolved_fields():
    staff, dr = central(STAFF), central(DR)
    ref = new_referral("MR-330", procedure=None)
    rid = ref["id"]
    up = ok(upload(rid, "unreadable_scan.png", "prescription", "image/png"), 201)
    wait_job(up["job"]["id"])
    manual = ok(staff.post(f"/referrals/{rid}/evidence/manual", {
        "category": "medication", "document_id": up["document"]["id"], "page": 1,
        "fields": {"medication": "Salbutamol inhaler", "dosage_text": "2 puffs as needed"}, "note": "Read from paper copy"}), 201)
    assert manual["origin"] == "manual" and manual["verification_status"] == "unverified"
    assert "Hina Raza" in manual["source_text"]
    items = ok(dr.get(f"/referrals/{rid}/review-items"))
    assert any(i["item_key"] == f"CL-DOC-FIELDS:{manual['id']}" and i["status"] == "open" for i in items)
    unresolved = ok(staff.post(f"/evidence/{manual['id']}/unresolve", {"note": "Strength unclear on copy"}))
    assert unresolved["review_state"] == "unresolved"
    ex = ok(staff.post(f"/evidence/{manual['id']}/exclude", {"note": "Not relevant"}))
    assert ex["review_state"] == "excluded" and ex["selected"] is False
    meds = ok(dr.get(f"/referrals/{rid}/medications"))["entries"]
    assert all(m["evidence_id"] != manual["id"] for m in meds)  # excluded evidence leaves the medication list
