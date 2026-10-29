"""Runs scripts/loadtest.py UNCHANGED except that sign-ins are serialised with a short gap, because Keycloak
brute-force protection rejects near-simultaneous logins to the same account (only 3 accounts are shared by
10 virtual users). Also counts how many virtual users actually started."""
import importlib.util, sys, threading, time
spec = importlib.util.spec_from_file_location("loadtest", "/scripts/loadtest.py"); lt = importlib.util.module_from_spec(spec); spec.loader.exec_module(lt)
_orig, _lock, started = lt.get_token, threading.Lock(), []
def staggered(user):
    with _lock:
        t = _orig(user); time.sleep(1.2); started.append(user); return t
lt.get_token = staggered
sys.argv = ["loadtest.py", "--users", "10", "--seconds", "60"]
lt.main()
print("VIRTUAL USERS SIGNED IN:", len(started))
