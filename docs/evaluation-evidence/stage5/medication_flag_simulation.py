"""Stage 5 medication-flag simulation. Runs the REAL service/router/package code in one DB session.
The draft rules are treated as approved ONLY inside this session; session.commit is redirected to flush and
everything is rolled back at the end, so no approval, flag, review or package persists.
Usage (inside central, -w /srv): python sim.py <referral_id> <clinician_subject_id>"""
import copy, json, re, sys
sys.path.insert(0, "/srv")
from app.db import SessionLocal
from app.models import (EvidenceItem, FlagReview, MedicationEntry, MedicationFlag, Referral, ReferralPackage,
                        ReviewItem, RuleApproval, SourceRetrieval, Clarification)
from app.medications import evaluator as E, router as MR, rules as RL, service as SV
from app.approvals import packages as PK
from app.generation import router as GR
from refcommon.auth import Principal

RID, SUB = int(sys.argv[1]), sys.argv[2]
P = Principal(subject=SUB, username="dr.malik", display_name="Sana Malik", institution_id="clinic-a",
              roles=frozenset({"clinician"}), client_id="sim", token="sim")
db = SessionLocal()
db.commit = db.flush  # nothing is committed
TEXTS = set()
OUT = []


def say(*a):
    line = " ".join(str(x) for x in a); print(line); OUT.append(line)


def ref():
    return db.get(Referral, RID)


def entry(sub):
    return [e for e in SV.current_entries(db, RID) if sub.lower() in e.original_name.lower()][0]


def run(label, trigger="stage5"):
    r = SV.reevaluate(db, ref(), trigger, "Stage 5 simulation", P)
    fl = SV.active_flags(db, RID)
    for f in fl:
        TEXTS.update([f.title, f.message])
    TEXTS.add(r.summary_message or "")
    say(f"[{label}] run={r.status} outcome={r.outcome} changed={r.changed_flags} error={r.error!r}")
    say(f"    summary: {r.summary_message}")
    for f in fl:
        say(f"    flag#{f.id} v{f.version} {f.kind} | {f.title} | med={f.medication} | use={f.current_use_status} | "
            f"src={f.source_label} | rule={f.rule_id} v{f.rule_version} | ev={f.evidence_ids}")
    return r


def use(sub, status):
    e = entry(sub); e.use_status = status; db.flush()


def proc(status, p=None):
    r = ref(); r.procedure_status, r.planned_procedure = status, p; db.flush()


def manual(name, dose="", origin="manual"):
    ev = EvidenceItem(referral_id=RID, patient_institution="clinic-a", patient_local_id=ref().patient_local_id, origin=origin,
                      source_institution="clinic-a", category="medication", display=f"{name} (manual)",
                      original={"medication": name, "record_kind": "manual", "dosage_text": dose},
                      current={"medication": name, "record_kind": "manual", "dosage_text": dose},
                      review_state="manual", verification_status="unverified", selected=True, author="Sana Malik")
    db.add(ev); db.flush(); SV.sync_entries(db, ref()); return ev


try:
    say("=== M0 live rules state:", [(r["rule_id"], r["version"], r["approval_state"]) for r in RL.all_rules(db, "orthodontics")])
    run("M0 no approved rules")
    for rule in RL.ruleset("orthodontics")["rules"]:
        db.add(RuleApproval(rule_id=rule["rule_id"], rule_version=rule["version"], content_hash=RL.rule_hash(rule),
                            status="approved", reviewer="STAGE 5 SIMULATION (rolled back)", reviewer_id="sim",
                            reference_checked="simulation only - not a clinical approval"))
    db.flush()
    say("=== simulated approvals:", [(r["rule_id"], r["approval_state"]) for r in RL.all_rules(db, "orthodontics")])

    base = db.begin_nested()
    say("\n=== M1 all medications unverified, procedure not stated")
    run("M1")

    say("\n=== M2 warfarin confirmed current + tooth extraction")
    use("warfarin", "confirmed_current"); proc("known", "tooth_extraction"); run("M2")

    say("\n=== M3 same medication and specialty, each procedure")
    for p in ["orthodontic_assessment", "fixed_appliance", "tooth_extraction", "mini_implant_placement", "orthognathic_surgery"]:
        proc("known", p)
        r = SV.reevaluate(db, ref(), "proc", "sim", P)
        say(f"    {p:24} outcome={r.outcome:12} flags={[(f.kind, f.rule_id) for f in SV.active_flags(db, RID) if f.kind != 'ambiguous_mapping']}")

    say("\n=== M4 procedure unknown / not stated (warfarin confirmed)")
    proc("unknown"); run("M4 unknown")
    proc("not_stated"); run("M4 not_stated")
    base.rollback(); base = db.begin_nested()

    say("\n=== M5 stopped prescription (Alendronate, source status 'stopped')")
    say("    source_status:", entry("alendronate").source_status, "| use_status:", entry("alendronate").use_status)
    proc("known", "tooth_extraction"); run("M5 stopped at source, use unverified")
    use("alendronate", "historical_stopped"); run("M5 clinician marked historical_stopped")
    use("alendronate", "confirmed_current"); proc("known", "orthodontic_assessment"); run("M5 confirmed, assessment (specialty-only rule)")
    base.rollback(); base = db.begin_nested()

    say("\n=== M6 uncertain / conflicting / unverified use (Ecosprin -> aspirin, antiplatelet)")
    proc("known", "tooth_extraction")
    for st in ["unverified", "uncertain", "conflicting"]:
        use("ecosprin", st)
        r = SV.reevaluate(db, ref(), "use", "sim", P)
        f = [x for x in SV.active_flags(db, RID) if "aspirin" in (x.flag_key or "")]
        say(f"    use={st:12} -> {[(x.kind, x.title, x.current_use_status) for x in f]}")
        for x in f: TEXTS.update([x.title, x.message])
    base.rollback(); base = db.begin_nested()

    say("\n=== M7 ambiguous / unmapped names, clinician mapping")
    manual("Disprin 300 mg", "300 mg"); manual("Herbal remedy Q", "1 sachet"); run("M7 with Disprin (suggested) and an unknown name")
    d = entry("disprin")
    say(f"    Disprin mapping: {d.mapping_status} note={d.mapping_note!r}; Herbal: {entry('herbal').mapping_status}")
    try:
        MR.set_mapping(RID, d.id, MR.MapIn(ingredient="disprinol", note="probe unknown ingredient"), db, P)
    except Exception as exc:
        say("    set_mapping to non-reviewed ingredient ->", getattr(exc, "status_code", ""), getattr(exc, "detail", exc))
    MR.set_mapping(RID, d.id, MR.MapIn(ingredient="aspirin", note="Disprin is aspirin 300 mg (checked pack)"), db, P)
    MR.set_use(RID, entry("disprin").id, MR.UseIn(use_status="confirmed_current", note="patient confirms"), db, P)
    proc("known", "tooth_extraction"); run("M7 after clinician mapping + confirmed")
    say("    mapping record:", entry("disprin").mapping_status, entry("disprin").mapping_source, entry("disprin").mapping_note)
    use("calcium", "historical_stopped"); run("M7 ambiguous but historical")
    base.rollback(); base = db.begin_nested()

    say("\n=== M8 medication source unavailable / denied alongside a confirmed flag")
    use("warfarin", "confirmed_current"); proc("known", "tooth_extraction")
    for st in ["unavailable", "denied"]:
        db.add(SourceRetrieval(referral_id=RID, source_institution="clinic-a", local_patient_id=ref().patient_local_id,
                               status=st, message=f"simulated {st}", requested_by="sim")); db.flush()
        run(f"M8 clinic {st}")
    base.rollback(); base = db.begin_nested()

    say("\n=== M9 evaluation failure vs genuine no-match")
    use("warfarin", "confirmed_current"); proc("known", "tooth_extraction"); run("M9 before failure")
    orig = RL.active_rules
    RL.active_rules = lambda db_, sp: [E.Rule("BROKEN", 1, "anticoagulant", "orthodontics", True, (), "t", "m")]
    run("M9 failure (malformed rule)")
    blk = PK.approval_blockers(db, ref())
    say("    approval blockers after failure:", [(b["type"], b["message"]) for b in blk if "evaluation" in b["type"]])
    RL.active_rules = orig
    use("warfarin", "historical_stopped"); use("ecosprin", "historical_stopped"); run("M9 genuine no-match")
    base.rollback(); base = db.begin_nested()

    say("\n=== M10 repeated evaluation and duplicate matches")
    use("warfarin", "confirmed_current"); proc("known", "tooth_extraction"); run("M10 first")
    n0 = db.query(MedicationFlag).filter(MedicationFlag.referral_id == RID).count()
    for i in range(3):
        r = SV.reevaluate(db, ref(), "repeat", "sim", P); say(f"    repeat {i+1}: changed={r.changed_flags} outcome={r.outcome}")
    say("    flag rows before/after repeats:", n0, db.query(MedicationFlag).filter(MedicationFlag.referral_id == RID).count())
    manual("Warfarin 5 mg tablet", "5 mg once daily"); use("warfarin 5 mg tablet (manual)" if False else "warfarin", "confirmed_current")
    for e in SV.current_entries(db, RID):
        if "warfarin" in e.original_name.lower(): e.use_status = "confirmed_current"
    db.flush(); run("M10 same drug from a second record (clinic + manual)")
    base.rollback(); base = db.begin_nested()

    say("\n=== M11 review, package traceability and changes")
    use("warfarin", "confirmed_current"); proc("known", "tooth_extraction"); run("M11 setup")
    f1 = [f for f in SV.active_flags(db, RID) if f.kind == "confirmed"][0]
    MR.review_flag(RID, f1.id, MR.FlagReviewIn(action="reviewed", flag_version=f1.version, note="Acknowledged"), db, P)
    GR.from_template(RID, db, P)
    r = ref(); r.status = "awaiting_approval"; r.referring_clinician_id = SUB; r.referring_clinician_name = "Sana Malik"
    r.priority = "routine"
    for ri in db.query(ReviewItem).filter(ReviewItem.referral_id == RID, ReviewItem.status == "open"):
        ri.status = "overridden"  # fixture shortcut inside the rolled-back session
    for f in SV.unreviewed_flags(db, RID):
        MR.review_flag(RID, f.id, MR.FlagReviewIn(action="reviewed", flag_version=f.version), db, P)
    db.flush()
    pkg = PK.approve(db, ref(), P, False, None); db.flush()
    env1 = copy.deepcopy(pkg.envelope)
    fs = [x for x in env1["medication_flags"] if x["kind"] == "confirmed"][0]
    say("    package v1 flag snapshot:", json.dumps(fs)[:600])
    say("    brief sections in package:", [s["key"] for s in env1["brief_sections"]], "| flags carried separately:", len(env1["medication_flags"]))
    rv = db.query(FlagReview).filter(FlagReview.flag_id == f1.id).all()
    say("    review rows:", [(x.reviewer, x.created_at.isoformat(), x.flag_version, x.action, x.clarification_id, x.side) for x in rv])

    say("  -- (a) procedure change extraction -> mini-implant (same rule still applies)")
    proc("known", "mini_implant_placement"); run("M11a")
    say("    referral:", ref().status, "| package v1 superseded:", db.get(ReferralPackage, pkg.id).superseded)

    say("  -- (b) procedure change -> fixed appliance (rule no longer applies)")
    proc("known", "fixed_appliance"); run("M11b")
    say("    referral:", ref().status, "| package v1 superseded:", db.get(ReferralPackage, pkg.id).superseded)
    proc("known", "tooth_extraction"); run("M11b back to extraction")
    f2 = [f for f in SV.active_flags(db, RID) if f.kind == "confirmed"][0]
    say("    flag after return:", f"#{f2.id} v{f2.version}", "| unreviewed blockers:", [b["message"] for b in PK.approval_blockers(db, ref()) if b["type"] == "flag_review"])
    try:
        MR.review_flag(RID, f1.id, MR.FlagReviewIn(action="reviewed", flag_version=f1.version), db, P)
    except Exception as exc:
        say("    re-review of old flag version ->", exc.status_code, exc.detail)

    say("  -- (c) rule version change (simulated v2 of ORTHO-ANTICOAG-SURG, approved)")
    rs = copy.deepcopy(RL.ruleset("orthodontics"))
    for x in rs["rules"]:
        if x["rule_id"] == "ORTHO-ANTICOAG-SURG":
            x["version"] = 2; x["message"] = x["message"] + " (wording revised in v2)"
            db.add(RuleApproval(rule_id=x["rule_id"], rule_version=2, content_hash=RL.rule_hash(x), status="approved",
                                reviewer="STAGE 5 SIMULATION", reviewer_id="sim", reference_checked="simulation only"))
    orig_rs = RL.ruleset
    RL.ruleset = lambda sp="orthodontics": rs
    run("M11c")
    say("    referral:", ref().status, "| unreviewed blockers:", [b["message"] for b in PK.approval_blockers(db, ref()) if b["type"] == "flag_review"])

    say("  -- (d) rule text edited WITHOUT a new approval (same version)")
    for x in rs["rules"]:
        if x["rule_id"] == "ORTHO-ANTICOAG-SURG":
            x["message"] = x["message"] + " edited"
    say("    approval state:", [(r["rule_id"], r["version"], r["approval_state"]) for r in RL.all_rules(db) if r["rule_id"] == "ORTHO-ANTICOAG-SURG"])
    run("M11d")
    RL.ruleset = orig_rs

    say("  -- (e) use change confirmed -> uncertain")
    use("warfarin", "uncertain"); run("M11e")
    use("warfarin", "confirmed_current"); run("M11e restore")

    say("  -- (f) change after submission (fixture: status submitted with v1 delivered)")
    r = ref(); r.status = "submitted"; r.submitted_package_version = pkg.version; r.current_package_version = pkg.version
    db.flush()
    proc("known", "fixed_appliance"); run("M11f")
    r = ref()
    say("    after: status", r.status, "| amendment_open", r.amendment_open, "| package v1 envelope unchanged:", db.get(ReferralPackage, pkg.id).envelope == env1)

    say("  -- (g) flag review with clarification request, including an unrelated assignee")
    proc("known", "tooth_extraction"); SV.reevaluate(db, ref(), "x", "sim", P)
    r.status = "draft"; r.amendment_open = False; db.flush()
    fx = [f for f in SV.active_flags(db, RID) if f.kind == "confirmed"][0]
    for assignee in ["lab-b", "spec-c", "no-such-institution"]:
        try:
            out = MR.review_flag(RID, fx.id, MR.FlagReviewIn(action="request_clarification", flag_version=fx.version,
                                                             question="Is warfarin still current?", assignee_institution=assignee), db, P)
            c = db.query(Clarification).filter(Clarification.flag_id == fx.id).order_by(Clarification.id.desc()).first()
            say(f"    assignee={assignee}: accepted, clarification #{c.id} assignee={c.assignee_institution}")
        except Exception as exc:
            say(f"    assignee={assignee}: rejected {getattr(exc, 'status_code', '')} {getattr(exc, 'detail', exc)}")
    rv = db.query(FlagReview).filter(FlagReview.flag_id == fx.id).all()
    say("    review rows:", [(x.reviewer, x.flag_version, x.action, x.clarification_id) for x in rv])
    try:
        MR.review_flag(RID, fx.id, MR.FlagReviewIn(action="request_clarification", flag_version=fx.version, question=""), db, P)
    except Exception as exc:
        say("    clarification without question ->", exc.status_code, exc.detail)
    base.rollback()

    say("\n=== M12 determinism of the pure evaluator")
    inp, _ = SV.build_input(db, ref())
    rules_all = tuple(E.Rule.from_dict(x) for x in RL.ruleset("orthodontics")["rules"])
    meds = tuple(MedInputs := [E.MedInput(m.entry_id, m.original_name, m.ingredient, m.drug_class, m.mapping_status,
                                          "confirmed_current", m.source_label, m.evidence_ids) for m in inp.medications])
    i1 = E.EvalInput("orthodontics", "known", "tooth_extraction", meds, inp.sources, rules_all)
    i2 = E.EvalInput("orthodontics", "known", "tooth_extraction", tuple(reversed(meds)), inp.sources, tuple(reversed(rules_all)))
    a, b, c = E.evaluate_medications(i1), E.evaluate_medications(i1), E.evaluate_medications(i2)
    key = lambda o: sorted(json.dumps(x.content(), sort_keys=True) for x in o.candidates)
    say("    same input twice identical:", key(a) == key(b), "| reordered meds+rules identical:", key(a) == key(c),
        "| order of candidates identical:", [x.flag_key for x in a.candidates] == [x.flag_key for x in c.candidates])
    TEXTS.update(t for x in a.candidates for t in (x.title, x.message)); TEXTS.add(a.summary_message)

    say("\n=== M13 wording scan (all generated titles/messages/summaries + rule file text)")
    for x in RL.ruleset("orthodontics")["rules"]:
        TEXTS.update([x["title"], x["message"]])
    bad = re.compile(r"\b(stop|stopping|discontinue|withhold|hold|start|switch|increase|decrease|reduce|bridge|urgent|urgently|"
                     r"immediately|safe|safely|cleared|clearance|contraindicated|must not|do not proceed)\b", re.I)
    hits = sorted({(m.group(0), t) for t in TEXTS if t for m in [bad.search(t)] if m})
    say(f"    {len(TEXTS)} distinct texts scanned; matches: {hits}")
finally:
    db.rollback(); db.close()
    with SessionLocal() as chk:
        say("\n[cleanup] persisted rule approvals:", chk.query(RuleApproval).count(),
            "| flags on referral:", chk.query(MedicationFlag).filter(MedicationFlag.referral_id == RID).count(),
            "| packages on referral:", chk.query(ReferralPackage).filter(ReferralPackage.referral_id == RID).count())
    open("/tmp/s5/sim-output.txt", "w").write("\n".join(OUT))
