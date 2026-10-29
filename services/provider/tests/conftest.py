"""Unit checks of the institution adapter's policy and release checks (no database, no network).

The provider image has no test tools, so they run in the central image with this service mounted:
  docker compose run --rm --no-deps -v ${PWD}/services/provider:/prov -w /prov -e INSTITUTION_ID=chughtai central python -m pytest tests -q
"""
import os

os.environ.setdefault("INSTITUTION_ID", "chughtai")
os.environ.setdefault("DATABASE_URL", "sqlite://")
