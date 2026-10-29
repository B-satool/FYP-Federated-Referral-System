"""Test and scan orders (kind=test). Spec v4 keeps the existing order flow for these: the laboratory performs the test
and keeps its own record; encrypting orders is future work (docs/e2e-mapping.md, "Out of scope for v4").

Test request: MRCP at Aga Khan radiology and liver tests at Chughtai Lab, sent as orders; results come back to
the doctor with the image.
"""
from __future__ import annotations

import base64

import httpx
from conftest import TINY_PNG, new_test_request
from helpers import CENTRAL, central, institution, ok, token, wait_for

DOCTOR, STAFF = central("dr.ali"), central("staff.ali")


def _ref(rid):
    return ok(STAFF.get(f"/referrals/{rid}"))


def test_p3_test_request_flow():
    """P3 (Abdul Rehman Gondal): MRI knee at AKUH radiology (never seen there) and blood tests at
    Chughtai Lab (known there)."""
    tests = [
        {"category": "imaging", "test": "MRI knee", "body_area": "Right knee", "urgency": "soon",
         "clinical_question": "Worsening knee pain; assess cartilage and menisci",
         "destination_institution": "akuh", "destination_department": "radiology"},
        {"category": "laboratory", "test": "Liver function tests", "urgency": "soon",
         "clinical_question": "Long-term diclofenac; check liver tests", "destination_institution": "chughtai",
         "destination_department": "laboratory"},
    ]
    r = new_test_request("Gondal", tests)
    assert r["kind"] == "test" and r["reference"].startswith("TST-") and r["destination_institution"] is None
    rid = r["id"]
    dxs = _ref(rid)["diagnostics"]
    mrcp = next(d for d in dxs if d["test"] == "MRI knee")
    lft = next(d for d in dxs if d["test"] == "Liver function tests")

    # Staff send both orders; no patient link is needed first.
    ok(STAFF.post(f"/diagnostics/{mrcp['id']}/send"))
    assert _ref(rid)["status"] == "requested"
    ok(STAFF.post(f"/diagnostics/{lft['id']}/send"))
    assert _ref(rid)["status"] == "submitted"

    # Chughtai already knows the patient (records link), so the order arrives matched.
    lab = institution("chughtai", "lab.chughtai")
    order = wait_for(lambda: next((o for o in ok(lab.get("/orders")) if o["order_ref"] == lft["reference"]), None), 60,
                     what="order at Chughtai")
    assert order["local_patient_id"]
    ok(lab.post(f"/orders/{order['id']}/accept"))
    assert lab.post(f"/orders/{order['id']}/report", {"findings": "normal"}).status_code == 422  # values required
    ok(lab.post(f"/orders/{order['id']}/report", {"values": [
        {"test": "ALT", "value": "52", "unit": "U/L", "reference": "7-56"},
        {"test": "Bilirubin (total)", "value": "0.9", "unit": "mg/dL", "reference": "0.3-1.2"}]}))

    # AKUH radiology has never seen the patient: they confirm (register as new) when the order arrives.
    rad = institution("akuh", "rad.aku")
    order = wait_for(lambda: next((o for o in ok(rad.get("/orders")) if o["order_ref"] == mrcp["reference"]), None), 60,
                     what="order at AKUH radiology")
    assert order["local_patient_id"] is None and order["link_request_id"]
    assert rad.post(f"/orders/{order['id']}/accept").status_code == 409
    ok(central("rad.aku").post(f"/patient-links/{order['link_request_id']}/lookup"))
    ok(central("rad.aku").post(f"/patient-links/{order['link_request_id']}/approve",
                               {"register_new": True, "note": "New patient; CNIC checked at the desk"}))
    ok(rad.post(f"/orders/{order['id']}/accept"))
    report = {"findings": "Medial compartment cartilage thinning; degenerate tear of the medial meniscus.",
              "impression": "Medial compartment osteoarthritis."}
    no_images = rad.post(f"/orders/{order['id']}/report", report)
    assert no_images.status_code == 422 and no_images.json()["detail"]["code"] == "images_required"
    ok(rad.post(f"/orders/{order['id']}/report", {**report, "attachments": [
        {"filename": "mri-knee-coronal.png", "content_type": "image/png", "data": TINY_PNG}]}))

    # Results come back to the doctor, with the image.
    wait_for(lambda: _ref(rid)["status"] == "response_returned", 60, what="all results")
    staff_view = {d["test"]: d for d in _ref(rid)["diagnostics"]}  # staff: test names and statuses only
    assert staff_view["MRI knee"]["report"] is None and staff_view["MRI knee"]["attachments"] == []
    dxs = {d["test"]: d for d in ok(DOCTOR.get(f"/referrals/{rid}"))["diagnostics"]}
    assert dxs["MRI knee"]["attachments"][0]["filename"] == "mri-knee-coronal.png"
    img = httpx.get(f"{CENTRAL}/diagnostics/{dxs['MRI knee']['id']}/attachments/1",
                    headers={"Authorization": f"Bearer {token('dr.ali')}"}, timeout=30)
    assert img.status_code == 200 and img.content == base64.b64decode(TINY_PNG)
    assert httpx.get(f"{CENTRAL}/diagnostics/{dxs['MRI knee']['id']}/attachments/1",
                     headers={"Authorization": f"Bearer {token('staff.ali')}"}, timeout=30).status_code == 403
    assert len(dxs["Liver function tests"]["report"]["values"]) == 2

    # The doctor sees each result; staff tell the patient and close.
    assert STAFF.post(f"/referrals/{rid}/close", {"expected_version": _ref(rid)["row_version"]}).status_code == 409
    for d in dxs.values():
        ok(DOCTOR.post(f"/diagnostics/{d['id']}/seen"))
    ok(STAFF.post(f"/referrals/{rid}/patient-informed", {"note": "Phoned the patient with the results"}))
    assert ok(STAFF.post(f"/referrals/{rid}/close", {"expected_version": _ref(rid)["row_version"]}))["status"] == "closed"
