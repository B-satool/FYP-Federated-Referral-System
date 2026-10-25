"""End-to-end v2 flow for P5 (Imtiaz Ali Soomro): Dr Ali's Clinic -> Aga Khan University
Hospital, General Surgery, laparoscopic cholecystectomy. Expected results come from
seed-data/patients/P5_imtiaz-ali-soomro.json (scenario and expected_retrieval_view)."""
from __future__ import annotations

from conftest import new_referral
from helpers import central, institution, ok, wait_for

DOCTOR, STAFF = central("dr.ali"), central("staff.ali")


def _ref(rid):
    return ok(STAFF.get(f"/referrals/{rid}"))


def test_p5_full_flow():
    # 1. The doctor fills in the form; staff cannot.
    denied = central("staff.ali").post("/referrals", {"patient_local_id": "DA-6120", "destination_institution": "akuh",
                                                      "destination_department": "general_surgery"})
    assert denied.status_code == 403
    r = new_referral("Imtiaz", "akuh", "general_surgery", "laparoscopic_cholecystectomy", diagnostics=[
        {"category": "imaging", "test": "MRCP", "body_area": "Abdomen", "urgency": "routine",
         "clinical_question": "Liver enzymes mildly raised; exclude a common bile duct stone",
         "destination_institution": "ziauddin", "destination_department": "radiology"}])
    assert r["status"] == "requested" and r["requesting_doctor_name"] == "Dr Ali Raza"
    rid = r["id"]

    # 2. AKUH staff (the other side) confirm the patient; nobody else can.
    incoming = ok(central("staff.aku").get("/patient-links/incoming"))
    link = next(x for x in incoming if x["referral_id"] == rid)
    assert central("staff.ali").post(f"/patient-links/{link['id']}/approve",
                                     {"register_new": True, "note": "x" * 5}).status_code == 403
    looked = ok(central("staff.aku").post(f"/patient-links/{link['id']}/lookup"))
    assert looked["candidates"] == []  # never seen at AKUH before
    approved = ok(central("staff.aku").post(f"/patient-links/{link['id']}/approve",
                                            {"register_new": True, "note": "New patient; CNIC and date of birth checked"}))
    assert approved["status"] == "verified" and approved["target_local_id"].startswith("AK-")

    # 3. Retrieval: own clinic + most recent hospital (Ziauddin) + lab; AKUH skipped (no visits there yet).
    res = ok(STAFF.post(f"/referrals/{rid}/retrieve"))["results"]
    by = {x["source_institution"]: x for x in res}
    assert by["drali"]["status"] == "successful"
    assert by["chughtai"]["status"] == "successful"
    assert by["ziauddin"]["status"] == "successful"
    assert by["akuh"]["status"] == "skipped", by["akuh"]

    # 4. Current medicines only (hyoscine was stopped) and exactly the expected flags.
    meds = ok(STAFF.get(f"/referrals/{rid}/medications"))
    names = {m["ingredient"] for m in meds["entries"] if not m["duplicate_of"]}
    assert names == {"insulin glargine", "metformin", "aspirin", "clopidogrel", "atorvastatin", "bisoprolol"}, names
    flags = {(f["rule_id"], f["medication"]) for f in meds["flags"] if f["kind"] == "confirmed"}
    assert {f[0] for f in flags} == {"RULE-002", "RULE-006", "RULE-007"}, flags
    assert len([f for f in flags if f[0] == "RULE-002"]) == 2  # aspirin and clopidogrel

    # 5. Staff add an over-the-counter medicine; a duplicate of a recorded one is shown once.
    ok(STAFF.post(f"/referrals/{rid}/medications/manual", {"name": "Panadol", "strength": "500 mg", "dose": "500 mg",
                                                            "frequency": "as needed", "over_the_counter": True}), 201)
    ok(STAFF.post(f"/referrals/{rid}/medications/manual", {"name": "Lipitor", "strength": "40 mg", "dose": "40 mg",
                                                            "frequency": "at night", "over_the_counter": False}), 201)
    meds = ok(STAFF.get(f"/referrals/{rid}/medications"))
    lipitor = [m for m in meds["entries"] if m["ingredient"] == "atorvastatin"]
    assert len(lipitor) == 2 and sum(1 for m in lipitor if m["duplicate_of"]) == 1
    assert any(m["over_the_counter"] and m["ingredient"] == "paracetamol" for m in meds["entries"])

    # 6. Not ready yet: medicines not confirmed with the patient, flags not acknowledged by the doctor.
    blockers = {i["key"] for i in _ref(rid)["readiness"] if i["blocking"] and not i["ok"]}
    assert blockers == {"meds_checked", "flags"}, blockers
    assert STAFF.post(f"/referrals/{rid}/send", {"expected_version": _ref(rid)["row_version"]}).status_code == 409
    ok(STAFF.post(f"/referrals/{rid}/medications/checked", {"note": "Asked about all medicines"}))
    # only the doctor acknowledges flags
    flag = meds["flags"][0]
    assert STAFF.post(f"/referrals/{rid}/flags/{flag['id']}/acknowledge", {"flag_version": flag["version"]}).status_code == 403
    for f in ok(DOCTOR.get(f"/referrals/{rid}/medications"))["flags"]:
        ok(DOCTOR.post(f"/referrals/{rid}/flags/{f['id']}/acknowledge", {"flag_version": f["version"]}))

    # 7. Staff send (doctors cannot); delivered to AKUH.
    r = _ref(rid)
    assert all(i["ok"] for i in r["readiness"] if i["blocking"]), r["readiness"]
    assert DOCTOR.post(f"/referrals/{rid}/send", {"expected_version": r["row_version"]}).status_code == 403
    sent = ok(STAFF.post(f"/referrals/{rid}/send", {"expected_version": r["row_version"]}))
    assert sent["package_version"] == 1
    wait_for(lambda: _ref(rid)["status"] == "submitted", 60, what="delivery")

    # 8. The test order goes to Ziauddin radiology (patient already linked there) and comes back.
    dx = _ref(rid)["diagnostics"][0]
    ok(STAFF.post(f"/diagnostics/{dx['id']}/send"))
    rad = institution("ziauddin", "rad.zia")
    order = wait_for(lambda: next((o for o in ok(rad.get("/orders")) if o["order_ref"] == dx["reference"]), None), 60,
                     what="order at Ziauddin")
    ok(rad.post(f"/orders/{order['id']}/accept"))
    ok(rad.post(f"/orders/{order['id']}/report", {"findings": "No common bile duct stone. Multiple gallbladder stones.",
                                                  "impression": "Cholelithiasis without choledocholithiasis."}))
    wait_for(lambda: _ref(rid)["diagnostics"][0]["status"] == "reported", 60, what="result returned")

    # 9. The receiving surgeon (department inbox) acknowledges, accepts and responds; sees the result too.
    surgeon = institution("akuh", "dr.naveed")
    case = wait_for(lambda: next((c for c in ok(surgeon.get("/cases")) if c["central_referral_id"] == r["reference"]), None),
                    30, what="case at AKUH")
    assert ok(institution("akuh", "dr.faisal").get("/cases")) == []  # dentistry does not see surgery referrals
    ok(surgeon.post(f"/cases/{case['id']}/acknowledge"))
    ok(surgeon.post(f"/cases/{case['id']}/decision", {"decision": "accept"}))
    wait_for(lambda: ok(surgeon.get(f"/cases/{case['id']}"))["results"], 60, what="forwarded MRCP result")
    resp = ok(surgeon.put(f"/cases/{case['id']}/response", {"assessment": "Symptomatic gallstones.",
                                                             "plan": "Laparoscopic cholecystectomy on the elective list.",
                                                             "instructions_for_clinic": "Cardiology input on antiplatelets.",
                                                             "appointment": "Surgical clinic in 2 weeks"}))
    ok(surgeon.post(f"/cases/{case['id']}/response/send", {"expected_row_version": resp["row_version"]}))
    wait_for(lambda: _ref(rid)["status"] == "response_returned", 60, what="response at the clinic")

    # 10. Doctor reviews, staff inform the patient, then close.
    response = ok(DOCTOR.get(f"/referrals/{rid}/responses"))[0]
    assert STAFF.post(f"/referrals/{rid}/close", {"expected_version": _ref(rid)["row_version"]}).status_code == 409
    ok(DOCTOR.post(f"/responses/{response['id']}/review", {"note": "Plan noted"}))
    ok(STAFF.post(f"/referrals/{rid}/patient-informed", {"note": "Phoned the patient; clinic date given"}))
    closed = ok(STAFF.post(f"/referrals/{rid}/close", {"expected_version": _ref(rid)["row_version"]}))
    assert closed["status"] == "closed"
