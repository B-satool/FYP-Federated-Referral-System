"""Grant close-out: central asks every institution to revoke the grants opened for a finished referral."""
from app.config import SOURCES, institution_url
from app.integration.grant_closeout import close_grants


def test_calls_every_source_with_the_referral_reference():
    calls = []
    out = close_grants("REF-1", lambda url, body: calls.append((url, body)) or {"revoked": 1})
    assert set(out) == set(SOURCES) and set(out.values()) == {"ok"}
    assert len(calls) == len(SOURCES)
    assert all(url.endswith("/grants/revoke-by-referral") and body["referral_ref"] == "REF-1" for url, body in calls)


def test_one_failing_source_is_reported_and_others_still_run():
    failing = sorted(SOURCES)[0]

    def post(url, body):
        if url.startswith(institution_url(failing)):
            raise RuntimeError("down")
        return {"revoked": 0}

    out = close_grants("REF-2", post)
    assert out[failing].startswith("RuntimeError")
    assert all(v == "ok" for k, v in out.items() if k != failing)
