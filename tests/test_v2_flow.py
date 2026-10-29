"""End-to-end v2 flows for P5 (Imtiaz Ali Soomro). Expected results come from
seed-data/patients/P5_imtiaz-ali-soomro.json (scenario and expected_retrieval_view).

1. Referral: Dr Ali's Clinic -> Aga Khan University Hospital, General Surgery.
   Doctor requests; staff gather and mark ready; doctor reviews flags; staff send;
   AKUH staff take it in, confirm the patient and assign the surgeon; the surgeon responds.
2. Test request: MRCP at Aga Khan radiology and liver tests at Chughtai Lab, sent as orders.
"""
from __future__ import annotations

import base64

import httpx
from conftest import SURGERY, TINY_PNG, new_referral, new_test_request
from helpers import CENTRAL, central, institution, ok, token, wait_for

DOCTOR, STAFF = central("dr.ali"), central("staff.ali")


def _ref(rid):
    return ok(STAFF.get(f"/referrals/{rid}"))


def _blockers(rid):
    return {i["key"] for i in _ref(rid)["readiness"] if i["blocking"] and not i["ok"]}


def test_p5_referral_flow():
    # 1. Only a doctor requests; tests are not part of a referral.
    denied = STAFF.post("/referrals", {"patient_local_id": "DA-6120", "destination_institution": "akuh",
                                       "destination_department": "general_surgery"})
    assert denied.status_code == 403
    r = new_referral("Imtiaz", "akuh", "general_surgery", "Laparoscopic cholecystectomy", SURGERY)
    assert r["status"] == "requested" and r["status_label"] == "In progress"
    assert r["procedure_label"] == "Laparoscopic cholecystectomy" and r["kind"] == "referral"
    rid = r["id"]
    # the destination is not asked anything until the referral is sent
    assert not [x for x in ok(central("staff.aku").get("/patient-links/incoming")) if x["referral_id"] == rid]

    # 2. Retrieval: own clinic + most recent hospital (Ziauddin) + lab. AKUH has no link yet.
    by = {x["source_institution"]: x for x in ok(STAFF.post(f"/referrals/{rid}/retrieve"))["results"]}
    assert {k: v["status"] for k, v in by.items()} == {"drali": "successful", "chughtai": "successful",
                                                       "ziauddin": "successful"}, by

    # 3. Only the doctor sees clinical content: staff get titles, counts and statuses (decision 2026-10-29).
    staff_meds = ok(STAFF.get(f"/referrals/{rid}/medications"))
    assert staff_meds["redacted"] and staff_meds["entries"] == [] and staff_meds["flags"] == [] and staff_meds["medicine_count"] >= 6
    staff_ev = ok(STAFF.get(f"/referrals/{rid}/evidence"))
    assert staff_ev and all(e["redacted"] and e["original"] == {} for e in staff_ev)
    assert any(e["display"].startswith("Lab result: ") for e in staff_ev)
    assert ok(DOCTOR.get(f"/referrals/{rid}"))["reason"] is not None and _ref(rid)["reason"] is None
    assert STAFF.get(f"/referrals/{rid}/brief-preview").status_code == 403

    # 4. Current medicines only (hyoscine was stopped) and exactly the expected flags (the doctor's view).
    meds = ok(DOCTOR.get(f"/referrals/{rid}/medications"))
    names = {m["ingredient"] for m in meds["entries"] if not m["duplicate_of"]}
    assert names == {"insulin glargine", "metformin", "aspirin", "clopidogrel", "atorvastatin", "bisoprolol"}, names
    flags = {(f["rule_id"], f["medication"]) for f in meds["flags"] if f["kind"] == "confirmed"}
    assert {f[0] for f in flags} == {"RULE-002", "RULE-006", "RULE-007"}, flags
    assert len([f for f in flags if f[0] == "RULE-002"]) == 2  # aspirin and clopidogrel

    # 5. Staff retrieve and mark it ready; they cannot see or change medicines, papers or records.
    flag = meds["flags"][0]
    assert DOCTOR.post(f"/referrals/{rid}/flags/{flag['id']}/acknowledge",
                       {"flag_version": flag["version"]}).status_code == 409  # not ready for review yet
    otc = {"name": "Panadol", "strength": "500 mg", "dose": "500 mg", "frequency": "as needed", "over_the_counter": True}
    assert STAFF.post(f"/referrals/{rid}/medications/manual", otc).status_code == 403
    assert STAFF.post(f"/evidence/{staff_ev[0]['id']}/select", {"selected": False}).status_code == 403
    assert _blockers(rid) == {"prepared", "meds_checked", "flags", "packet_reviewed"}, _blockers(rid)
    prepared = ok(STAFF.post(f"/referrals/{rid}/prepared", {"expected_version": _ref(rid)["row_version"]}))
    assert prepared["status_label"] == "With the doctor for review"
    queue = ok(DOCTOR.get("/work-queue"))
    assert any(x["id"] == rid for x in queue["flags_to_acknowledge"])

    # 6. The doctor adds what the patient reports (a duplicate is shown once), confirms the list, reviews the
    #    flags and the packet; staff cannot send before that, and the doctor cannot send at all.
    ok(DOCTOR.post(f"/referrals/{rid}/medications/manual", otc), 201)
    ok(DOCTOR.post(f"/referrals/{rid}/medications/manual", {"name": "Lipitor", "strength": "40 mg", "dose": "40 mg",
                                                             "frequency": "at night"}), 201)
    meds = ok(DOCTOR.get(f"/referrals/{rid}/medications"))
    lipitor = [m for m in meds["entries"] if m["ingredient"] == "atorvastatin"]
    assert len(lipitor) == 2 and sum(1 for m in lipitor if m["duplicate_of"]) == 1
    assert STAFF.post(f"/referrals/{rid}/medications/checked", {"note": "x"}).status_code == 403
    ok(DOCTOR.post(f"/referrals/{rid}/medications/checked", {"note": "Asked about all medicines"}))
    assert STAFF.post(f"/referrals/{rid}/flags/{flag['id']}/acknowledge",
                      {"flag_version": flag["version"]}).status_code == 403
    for f in ok(DOCTOR.get(f"/referrals/{rid}/medications"))["flags"]:
        ok(DOCTOR.post(f"/referrals/{rid}/flags/{f['id']}/acknowledge", {"flag_version": f["version"]}))
    r = _ref(rid)
    assert _blockers(rid) == {"packet_reviewed"}, r["readiness"]
    assert STAFF.post(f"/referrals/{rid}/send", {"expected_version": r["row_version"]}).status_code == 409
    assert STAFF.post(f"/referrals/{rid}/packet-reviewed", {"expected_version": r["row_version"]}).status_code == 403
    reviewed = ok(DOCTOR.post(f"/referrals/{rid}/packet-reviewed", {"expected_version": r["row_version"]}))
    assert reviewed["status_label"] == "Ready to send" and reviewed["packet_reviewed_by"]
    r = _ref(rid)
    assert not _blockers(rid), r["readiness"]
    assert STAFF.post(f"/referrals/{rid}/cancel", {"expected_version": r["row_version"], "reason": "test"}).status_code == 403
    assert DOCTOR.post(f"/referrals/{rid}/send", {"expected_version": r["row_version"]}).status_code == 403
    sent = ok(STAFF.post(f"/referrals/{rid}/send", {"expected_version": r["row_version"]}))
    assert sent["package_version"] == 1
    wait_for(lambda: _ref(rid)["status"] == "submitted", 60, what="delivery")
    assert ok(STAFF.get(f"/referrals/{rid}/packages/1"))["envelope"] is None  # staff: what was sent, not its content
    pkg = ok(DOCTOR.get(f"/referrals/{rid}/packages/1"))["envelope"]
    assert pkg["patient"]["cnic"] and pkg["patient"]["link_request_id"] and not pkg["patient"]["local_patient_id"]
    titles = [s["title"] for s in pkg["brief_sections"]]
    assert titles[:3] == ["Reason for referral", "Planned procedure", "Current medicines"], titles

    # 7. AKUH staff take it in; the surgeon sees nothing until it is assigned.
    aku_staff, surgeon = institution("akuh", "staff.aku"), institution("akuh", "dr.naveed")
    case = wait_for(lambda: next((c for c in ok(aku_staff.get("/cases")) if c["central_referral_id"] == r["reference"]),
                                 None), 30, what="case at AKUH")
    assert ok(surgeon.get("/cases")) == []
    ok(aku_staff.post(f"/cases/{case['id']}/acknowledge"))
    intake = ok(aku_staff.get(f"/cases/{case['id']}"))  # intake staff: who, how urgent, record titles; no content
    assert intake["redacted"] and intake["packages"][0]["envelope"] is None and intake["packages"][0]["record_titles"]
    assert aku_staff.post(f"/cases/{case['id']}/assign", {"doctor": "Dr Naveed Baig"}).status_code == 409  # patient first
    link_id = case["link_request_id"]
    assert ok(central("staff.aku").post(f"/patient-links/{link_id}/lookup"))["candidates"] == []
    approved = ok(central("staff.aku").post(f"/patient-links/{link_id}/approve",
                                            {"register_new": True, "note": "New patient; CNIC and date of birth checked"}))
    assert approved["status"] == "verified" and approved["kind"] == "intake" and approved["registered_new"]
    case = ok(aku_staff.get(f"/cases/{case['id']}"))["case"]
    assert case["local_patient_id"] == approved["target_local_id"]
    # the clinic is told the patient was new there, and that record is not a records source
    notes = ok(STAFF.get("/notifications"))
    assert any("registered" in n["title"] and "new patient" in n["title"] for n in notes)
    assert not any(s["institution_id"] == "akuh" and s["linked"] for s in _ref(rid)["sources"])
    ok(aku_staff.post(f"/cases/{case['id']}/assign", {"doctor": "Dr Naveed Baig", "note": "Gallstones"}))
    assert ok(institution("akuh", "dr.faisal").get("/cases")) == []

    # 8. The surgeon accepts; no response is written. The requesting doctor (and staff) are told.
    mine = ok(surgeon.get("/cases"))
    full = ok(surgeon.get(f"/cases/{case['id']}"))  # the assigned doctor sees the referral itself
    assert not full["redacted"] and full["packages"][0]["envelope"]["brief_sections"]
    assert [c["central_referral_id"] for c in mine] == [r["reference"]]
    ok(surgeon.post(f"/cases/{case['id']}/decision", {"decision": "accept"}))
    wait_for(lambda: _ref(rid)["status"] == "accepted", 60, what="acceptance at the clinic")
    assert any("accepted" in n["title"] for n in ok(DOCTOR.get("/notifications")))

    # 9. Staff tell the patient; then the doctor (or staff) close it.
    assert DOCTOR.post(f"/referrals/{rid}/close", {"expected_version": _ref(rid)["row_version"]}).status_code == 409
    ok(STAFF.post(f"/referrals/{rid}/patient-informed", {"note": "Phoned the patient; clinic date given"}))
    closed = ok(DOCTOR.post(f"/referrals/{rid}/close", {"expected_version": _ref(rid)["row_version"]}))
    assert closed["status"] == "closed" and closed["closed_by"] == "Dr Ali Raza"


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
    dxs = {d["test"]: d for d in ok(DOCTOR.get(f"/referrals/{rid}"))["diagnostics"]}  # results are clinical: the doctor's view
    assert dxs["MRI knee"]["attachments"][0]["filename"] == "mri-knee-coronal.png"
    img = httpx.get(f"{CENTRAL}/diagnostics/{dxs['MRI knee']['id']}/attachments/1",
                    headers={"Authorization": f"Bearer {token('dr.ali')}"}, timeout=30)
    assert img.status_code == 200 and img.content == base64.b64decode(TINY_PNG)
    assert len(dxs["Liver function tests"]["report"]["values"]) == 2

    # The doctor sees each result; staff tell the patient and close.
    assert STAFF.post(f"/referrals/{rid}/close", {"expected_version": _ref(rid)["row_version"]}).status_code == 409
    for d in dxs.values():
        ok(DOCTOR.post(f"/diagnostics/{d['id']}/seen"))
    ok(STAFF.post(f"/referrals/{rid}/patient-informed", {"note": "Phoned the patient with the results"}))
    assert ok(STAFF.post(f"/referrals/{rid}/close", {"expected_version": _ref(rid)["row_version"]}))["status"] == "closed"
