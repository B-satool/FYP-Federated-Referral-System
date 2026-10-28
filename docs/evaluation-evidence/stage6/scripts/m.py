import sys; sys.path.insert(0, "/tmp/s6")
from h import call
_, meds = call("A3-meds", "dr.malik", "GET", "central", "/referrals/6/medications", quiet=True)
e = [x for x in meds["entries"] if "Atorvastatin" in x["original_name"]][0]
print("before:", e["use_status"], "| entry fields:", sorted(k for k in e if "version" in k))
s1 = call("A3-use-1", "dr.malik", "POST", "central", f"/referrals/6/medications/{e['id']}/use", {"use_status": "confirmed_current", "note": "user 1 from screen loaded earlier"}, quiet=True)[0]
s2 = call("A3-use-2", "dr.locum", "POST", "central", f"/referrals/6/medications/{e['id']}/use", {"use_status": "historical_stopped", "note": "user 2 from the same earlier screen"}, quiet=True)[0]
_, m2 = call("A3-meds", "dr.malik", "GET", "central", "/referrals/6/medications", quiet=True)
x = [y for y in m2["entries"] if y["id"] == e["id"]][0]
print(f"two clinicians from the same screen: {s1}, {s2} -> final use_status={x['use_status']} by {x.get('use_verified_by')} (first change silently replaced)")
