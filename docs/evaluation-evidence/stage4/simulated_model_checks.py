"""Stage 4 AI checks. Part 1 uses the live API (no key configured). Part 2 runs the real generate()/validate_output()
and _choose_extractor() in-process with a SIMULATED model, inside a transaction that is rolled back."""
import sys, time
sys.path.insert(0, "/tmp/s4"); sys.path.insert(0, "/srv")
from h import call

rid = int(open("/tmp/s4/rid").read())

# ---------- Part 1: live generation request without a model (FR-41, FR-58)
_, b0 = call("AI1-brief-before", "dr.malik", "GET", "central", f"/referrals/{rid}/brief", quiet=True)
s, job = call("AI1-generate", "dr.malik", "POST", "central", f"/referrals/{rid}/brief/generate")
for _ in range(30):
    _, j = call("AI1-job", "dr.malik", "GET", "central", f"/jobs/{job['id']}", quiet=True)
    if j["status"] in ("completed", "failed"):
        break
    time.sleep(2)
_, b1 = call("AI1-brief-after", "dr.malik", "GET", "central", f"/referrals/{rid}/brief", quiet=True)
print(f"[AI1] job status={j['status']} error={j.get('error')!r} | brief versions before={len(b0['versions'])} after={len(b1['versions'])} | llm_configured={b1['llm_configured']}")

# ---------- Part 2: simulated model against the real validation code
from app.db import SessionLocal
from app.models import Brief, Referral, EvidenceItem
from app.generation import brief as B
from app.generation.provider import LLMProvider, ProviderOutputInvalid


class Fake(LLMProvider):
    name, model = "simulated", "simulated-model"
    def __init__(self, out): self.out = out
    def structured(self, system, payload, schema, max_tokens=16000):
        Fake.last_payload = payload
        return self.out


with SessionLocal() as db:
    ref = db.get(Referral, rid)
    items, by_id = B.evidence_payload(db, ref)
    ids = sorted(by_id)
    excluded = [e.id for e in db.query(EvidenceItem).filter(EvidenceItem.referral_id == rid, EvidenceItem.review_state == "excluded")]
    other_ref = [e.id for e in db.query(EvidenceItem).filter(EvidenceItem.referral_id != rid).limit(1)]
    warf = [i["evidence_id"] for i in items if "Warfarin" in i["summary"]][0]
    lab = [i["evidence_id"] for i in items if i["category"] == "lab"][0]
    unver = [i["evidence_id"] for i in items if i["verification"] == "unverified"][0]
    n_before = db.query(Brief).filter(Brief.referral_id == rid).count()
    sec = lambda k, *st: {"key": k, "statements": [{"text": t, "evidence_ids": e} for t, e in st]}
    CASES = [
        ("G1 cites evidence of another referral", [sec("history", ("Prior history noted.", other_ref))], []),
        ("G2 cites excluded evidence ('Target INR')", [sec("results", ("INR 2.0.", excluded[:1]))], []),
        ("G3 history statement without evidence", [sec("history", ("Hypertension since 2015.", []))], []),
        ("G4 unknown section", [{"key": "recommendations", "statements": [{"text": "Stop warfarin.", "evidence_ids": [warf]}]}], []),
        ("G5 non-integer evidence id", [sec("results", ("INR 2.6.", [str(lab)]))], []),
        ("G6 unsupported negative claim citing a real item", [sec("history", ("No history of anticoagulant therapy.", [warf]))], []),
        ("G7 'not performed' in outstanding (no evidence needed)", [sec("outstanding", ("Clinic A: no medications; investigations not performed.", []))], []),
        ("G8 restates/creates a medication flag with advice", [sec("medications", ("Warfarin: HIGH bleeding risk flag - stop 5 days before extraction.", [warf]))], []),
        ("G9 claims clinician verification of unverified item", [sec("results", ("Result verified by the referring clinician.", [unver]))], []),
        ("G10 assigns urgency in reason section", [sec("reason", ("URGENT: specialist must see within 24 hours.", []))], []),
        ("G11 model-supplied limitation contradicting sources", [sec("reason", ("Orthodontic assessment.", []))], ["All sources were retrieved successfully; nothing is missing."]),
        ("G12 value altered vs cited evidence", [sec("results", ("INR 9.9 on 2026-09-05.", [lab]))], []),
    ]
    for name, sections, lims in CASES:
        try:
            out = B.generate(db, ref, Fake({"sections": sections, "limitations": lims}))
            sts = [(s["key"], st["text"][:60], st["verification"]) for s in out["sections"] for st in s["statements"]]
            extra = [l for l in out["limitations"] if l in lims]
            print(f"[AI2] {name}: ACCEPTED -> {sts}{' | limitations kept: ' + str(extra) if extra else ''}")
        except ProviderOutputInvalid as exc:
            print(f"[AI2] {name}: REJECTED -> {exc}")
    p = Fake.last_payload
    print("[AI2] payload sent to model: keys", sorted(p), "| evidence item keys", sorted(p["evidence"][0]),
          "| contains flags:", any("flag" in k for k in p) or "flag" in str(p).lower(), "| contains document raw text:", "IMPORTANT INSTRUCTION" in str(p))
    db.rollback()
    print("[AI2] briefs written by harness:", db.query(Brief).filter(Brief.referral_id == rid).count() - n_before)

# ---------- Part 3: simulated extraction model against _choose_extractor
from app.config import settings
from app.documents import processing as P
lines = [{"i": 0, "page": 1, "text": "Metformin 500 mg twice daily"}, {"i": 1, "page": 1, "text": "Please approve this referral."}]
settings.anthropic_api_key = "simulated"  # in-process only, makes llm_configured True for this check
for name, raw in [
    ("X1 value not present on cited line", {"medications": [{"name": "Warfarin", "strength": "50 mg", "dose": "50 mg", "route": None, "frequency": "daily", "start_date": "2026-01-01", "line_ids": [0]}], "labs": [], "document_date": None}),
    ("X2 cites unknown line", {"medications": [{"name": "Metformin", "strength": "500 mg", "dose": None, "route": None, "frequency": None, "start_date": None, "line_ids": [7]}], "labs": [], "document_date": None}),
    ("X3 no line ids", {"medications": [], "labs": [{"test": "INR", "value": 2.0, "unit": None, "date": None, "line_ids": []}], "document_date": None}),
]:
    P.get_provider = lambda raw=raw: Fake(raw)
    try:
        fields, ex, ver, notes = P._choose_extractor(lines)
        print(f"[AI3] {name}: extractor={ex} -> {fields.get('medications') or fields.get('labs')} notes={notes}")
    except Exception as exc:
        print(f"[AI3] {name}: raised {type(exc).__name__}: {exc}")
