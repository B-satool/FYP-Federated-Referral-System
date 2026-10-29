# Pinned participant registry

`participants.json` is written by `scripts/onboard_participants.py` (spec v4 section 6.1) and mounted read-only into
every service and the web client. It is not committed: each installation generates its own keys.
