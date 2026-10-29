"""Creates demo referrals for the seed patients, at different stages, through the real APIs.

Run after a reset and seed, against the running Compose stack:
  .venv\\Scripts\\python scripts/seed_demo_referrals.py

Everything goes through the same endpoints the web app uses (doctor requests, staff gather and send,
the receiving institution takes it in), so each patient's view shows what a real journey leaves behind:
  P1 Rubina Akhtar          referral to AKUH Dentistry, accepted
  P2 Muhammad Tariq Mahmood referral to Ziauddin Cardiology, sent
  P3 Abdul Rehman Gondal    test request: liver tests reported at Chughtai Lab, knee MRI booked at AKUH
  P4 Shazia Parveen         referral to Ziauddin Gastroenterology, being prepared
  P5 Imtiaz Ali Soomro      referral to AKUH General Surgery, accepted, completed and closed
Synthetic data only.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from helpers import central, institution, ok, wait_for  # noqa: E402

DOCTOR, STAFF = central("dr.ali"), central("staff.ali")
SURGERY = ["major_surgery", "general_anaesthesia", "prolonged_fasting", "bleeding_risk"]


def _ref(rid: int) -> dict:
    return ok(DOCTOR.get(f"/referrals/{rid}"))


def request(patient: str, dest: str, dept: str, procedure: str, tags: list[str], reason: str, urgency: str) -> int:
    p = ok(DOCTOR.get("/patients/search", params={"q": patient}))[0]
    body = {"kind": "referral", "patient_local_id": p["local_patient_id"], "destination_institution": dest,
            "destination_department": dept, "reason": reason, "urgency": urgency, "procedure_status": "planned",
            "planned_procedure": procedure, "procedure_tags": tags, "submit": True}
    return ok(DOCTOR.post("/referrals", body), 201)["id"]


def prepare(rid: int) -> None:
    """Staff gather the records and mark it ready; the doctor confirms the medicines, decides every flag
    and reviews the packet."""
    ok(STAFF.post(f"/referrals/{rid}/retrieve"))
    ok(STAFF.post(f"/referrals/{rid}/prepared", {"expected_version": _ref(rid)["row_version"]}))
    # A medicine recorded with different doses at two places: the clinic's own (latest) prescription is
    # current, so the doctor excludes the other one, with the reason.
    by_ingredient: dict[str, list[dict]] = {}
    for e in ok(DOCTOR.get(f"/referrals/{rid}/medications"))["entries"]:
        if e["ingredient"] and not e["excluded"] and not e["duplicate_of"]:
            by_ingredient.setdefault(e["ingredient"], []).append(e)
    for entries in by_ingredient.values():
        if len({e["dose"] for e in entries}) > 1:
            keep = next((e for e in entries if e["source_label"].startswith("Dr Ali's Clinic")), entries[0])
            for e in entries:
                if e is not keep:
                    ok(DOCTOR.post(f"/referrals/{rid}/medications/{e['id']}/exclude",
                                   {"reason": "Older prescription; patient takes the dose on the clinic's latest prescription"}))
    ok(DOCTOR.post(f"/referrals/{rid}/medications/checked", {"note": "Asked about all medicines"}))
    for f in ok(DOCTOR.get(f"/referrals/{rid}/medications"))["flags"]:
        ok(DOCTOR.post(f"/referrals/{rid}/flags/{f['id']}/acknowledge", {"flag_version": f["version"]}))
    ok(DOCTOR.post(f"/referrals/{rid}/packet-reviewed", {"expected_version": _ref(rid)["row_version"]}))


def send(rid: int) -> str:
    ok(STAFF.post(f"/referrals/{rid}/send", {"expected_version": _ref(rid)["row_version"]}))
    wait_for(lambda: _ref(rid)["status"] == "submitted", 90, what="delivery")
    return _ref(rid)["reference"]


def take_in(inst: str, staff: str, reference: str, doctor: str) -> dict:
    """The receiving institution's staff acknowledge, confirm the patient and assign a doctor."""
    desk = institution(inst, staff)
    case = wait_for(lambda: next((c for c in ok(desk.get("/cases")) if c["central_referral_id"] == reference), None),
                    60, what=f"case at {inst}")
    ok(desk.post(f"/cases/{case['id']}/acknowledge"))
    case = ok(desk.get(f"/cases/{case['id']}"))["case"]
    if not case["local_patient_id"]:
        link = case["link_request_id"]
        found = ok(central(staff).post(f"/patient-links/{link}/lookup"))["candidates"]
        body = ({"local_patient_id": found[0]["local_patient_id"], "note": "CNIC and date of birth match"} if found
                else {"register_new": True, "note": "New patient; CNIC and date of birth checked"})
        ok(central(staff).post(f"/patient-links/{link}/approve", body))
    ok(desk.post(f"/cases/{case['id']}/assign", {"doctor": doctor}))
    return case


def accept(inst: str, doctor_user: str, case_id: int, rid: int) -> None:
    ok(institution(inst, doctor_user).post(f"/cases/{case_id}/decision", {"decision": "accept"}))
    wait_for(lambda: _ref(rid)["status"] == "accepted", 90, what="acceptance")


def p1_rubina() -> None:
    rid = request("Rubina", "akuh", "dentistry", "Surgical extraction of lower left molar", ["oral_surgery", "bleeding_risk"],
                  "Painful, partly erupted lower left wisdom tooth with repeated infections. On alendronate for "
                  "osteoporosis. Please assess for surgical extraction.", "soon")
    prepare(rid)
    case = take_in("akuh", "staff.aku", send(rid), "Dr Faisal Haider")
    accept("akuh", "dr.faisal", case["id"], rid)
    ok(STAFF.post(f"/referrals/{rid}/patient-informed", {"note": "Phoned the patient; AKUH will call with a date"}))


def p2_tariq() -> None:
    rid = request("Tariq", "ziauddin", "cardiology", "Coronary angiography", ["iodinated_contrast", "arterial_access"],
                  "Chest tightness on exertion for six weeks, positive exercise test. Diabetic on metformin. "
                  "Please assess for coronary angiography.", "urgent")
    prepare(rid)
    send(rid)


def p3_gondal_tests() -> None:
    tests = [
        {"category": "laboratory", "test": "Liver function tests", "urgency": "soon",
         "clinical_question": "Long-term diclofenac; check liver tests", "destination_institution": "chughtai",
         "destination_department": "laboratory"},
        {"category": "imaging", "test": "MRI knee", "body_area": "Right knee", "urgency": "soon",
         "clinical_question": "Worsening knee pain; assess cartilage and menisci",
         "destination_institution": "akuh", "destination_department": "radiology"},
    ]
    p = ok(DOCTOR.get("/patients/search", params={"q": "Gondal"}))[0]
    r = ok(DOCTOR.post("/referrals", {"kind": "test", "patient_local_id": p["local_patient_id"],
                                      "reason": "Knee pain on long-term diclofenac", "diagnostic_requests": tests,
                                      "submit": True}), 201)
    dxs = {d["test"]: d for d in _ref(r["id"])["diagnostics"]}
    for d in dxs.values():
        ok(STAFF.post(f"/diagnostics/{d['id']}/send"))
    lab = institution("chughtai", "lab.chughtai")
    order = wait_for(lambda: next((o for o in ok(lab.get("/orders"))
                                   if o["order_ref"] == dxs["Liver function tests"]["reference"]), None), 60, what="lab order")
    ok(lab.post(f"/orders/{order['id']}/accept"))
    ok(lab.post(f"/orders/{order['id']}/report", {"values": [
        {"test": "ALT", "value": "52", "unit": "U/L", "reference": "7-56"},
        {"test": "Bilirubin (total)", "value": "0.9", "unit": "mg/dL", "reference": "0.3-1.2"}]}))
    rad = institution("akuh", "rad.aku")
    order = wait_for(lambda: next((o for o in ok(rad.get("/orders"))
                                   if o["order_ref"] == dxs["MRI knee"]["reference"]), None), 60, what="MRI order")
    if not order["local_patient_id"]:
        found = ok(central("rad.aku").post(f"/patient-links/{order['link_request_id']}/lookup"))["candidates"]
        body = ({"local_patient_id": found[0]["local_patient_id"], "note": "CNIC matches"} if found
                else {"register_new": True, "note": "New patient; CNIC checked at the desk"})
        ok(central("rad.aku").post(f"/patient-links/{order['link_request_id']}/approve", body))
    ok(rad.post(f"/orders/{order['id']}/accept"))
    when = (datetime.now(timezone.utc) + timedelta(days=5)).replace(hour=10, minute=30, second=0, microsecond=0)
    ok(rad.post(f"/orders/{order['id']}/schedule", {"scheduled_for": when.isoformat()}))


def p4_shazia() -> None:
    rid = request("Shazia", "ziauddin", "gastro_hepatology", "Upper GI endoscopy", ["gi_endoscopy", "sedation"],
                  "Upper abdominal pain and heartburn for three months despite omeprazole; takes ibuprofen for "
                  "back pain. Please assess for upper GI endoscopy.", "routine")
    ok(STAFF.post(f"/referrals/{rid}/retrieve"))


def p5_imtiaz() -> None:
    rid = request("Imtiaz", "akuh", "general_surgery", "Laparoscopic cholecystectomy", SURGERY,
                  "Repeated right upper abdominal pain after fatty meals. Ultrasound shows multiple gallstones. "
                  "Diabetic with a coronary stent. Needs surgical assessment for gallbladder removal.", "routine")
    prepare(rid)
    case = take_in("akuh", "staff.aku", send(rid), "Dr Naveed Baig")
    accept("akuh", "dr.naveed", case["id"], rid)
    ok(institution("akuh", "dr.naveed").post(f"/cases/{case['id']}/complete"))
    wait_for(lambda: _ref(rid)["receiver_completed_at"], 90, what="completion notice from AKUH")
    ok(STAFF.post(f"/referrals/{rid}/patient-informed", {"note": "Phoned the patient; surgery date given"}))
    ok(DOCTOR.post(f"/referrals/{rid}/close", {"expected_version": _ref(rid)["row_version"]}))


if __name__ == "__main__":
    for step in (p1_rubina, p2_tariq, p3_gondal_tests, p4_shazia, p5_imtiaz):
        print(f"{step.__name__} ...", flush=True)
        step()
    print("Done. Patients sign in with their account (e.g. rubina.akhtar) and the demo password.")
