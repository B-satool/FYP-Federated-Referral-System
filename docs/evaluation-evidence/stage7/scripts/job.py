import sys, time, io; sys.path.insert(0, "/tmp/s7")
from h import call
from PIL import Image, ImageDraw, ImageFont
phase = sys.argv[1]
if phase == "upload":
    font = ImageFont.load_default(size=30); pages = []
    for i in range(10):
        img = Image.new("RGB", (1240, 1754), "white"); d = ImageDraw.Draw(img)
        d.text((60, 40), "SYNTHETIC SAMPLE - Stage 7 interrupted-job test - not a real patient", fill="black", font=ImageFont.load_default(size=18))
        for j in range(30):
            d.text((60, 100 + j * 52), f"Page {i+1} line {j+1}: Warfarin 5 mg once daily; INR 2.{j % 9}", fill="black", font=font)
        pages.append(img)
    buf = io.BytesIO(); pages[0].save(buf, format="PDF", save_all=True, append_images=pages[1:]); data = buf.getvalue()
    t0 = time.monotonic()
    s, o = call("J1-upload", "staff.a", "POST", "central", "/referrals/5/documents", files={"file": ("ten_page_scan.pdf", data, "application/pdf")}, data={"doc_type": "other"}, quiet=True)
    print(f"[J1] upload of 10-page scan -> HTTP {s} in {(time.monotonic()-t0)*1000:.0f} ms; document {o['document']['id']} status={o['document']['status']} job={o['job']['id'][:8]} status={o['job']['status']}")
    open("/tmp/s7/job", "w").write(f"{o['document']['id']} {o['job']['id']}")
    for _ in range(20):
        _, j = call("J1-job", "staff.a", "GET", "central", f"/jobs/{o['job']['id']}", quiet=True)
        if j["status"] == "running":
            print(f"[J1] job running (attempts={j.get('attempts')}) at +{time.monotonic()-t0:.1f}s"); break
        time.sleep(0.5)
else:
    doc, job = open("/tmp/s7/job").read().split()
    t0 = time.monotonic(); last = None
    while time.monotonic() - t0 < float(sys.argv[2]):
        _, j = call("J2-job", "staff.a", "GET", "central", f"/jobs/{job}", quiet=True)
        _, d = call("J2-doc", "staff.a", "GET", "central", f"/documents/{doc}", quiet=True)
        cur = (j["status"], j.get("attempts"), d["document"]["status"], (j.get("error") or "")[:80])
        if cur != last:
            print(f"[{phase}] +{time.monotonic()-t0:5.1f}s job={cur[0]} attempts={cur[1]} document={cur[2]} error={cur[3]!r}"); last = cur
        if j["status"] in ("completed", "failed"): break
        time.sleep(2)
    if phase == "after-restart":
        _, d = call("J2-doc", "staff.a", "GET", "central", f"/documents/{doc}", quiet=True)
        runs = d.get("extraction") or {}
        print(f"[{phase}] extraction run: status={runs.get('status')} pages={len(runs.get('pages') or [])} fields={len(d['fields'])} duration_ms={runs.get('duration_ms')}")
