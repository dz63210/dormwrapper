"""Pytest bootstrap: isolate the test run from the developer's environment.

Imported by pytest before any test module (and therefore before ``app.config``,
a ``pydantic-settings`` ``BaseSettings``, reads the environment). Setting real
OS env vars here overrides any value in ``backend/.env``, since pydantic-settings
ranks environment variables above the ``.env`` file.

Without this, ``pytest`` would pick up a local ``.env`` (e.g.
``RECOMMENDATION_PROVIDER=gemini``) and fire real API calls, and it would read
and write the real ``./data/app.db`` and ``./data/uploads``.
"""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="dormwrapper-tests-")

# Deterministic, offline AI stages.
os.environ["RECOMMENDATION_PROVIDER"] = "mock"
os.environ["IMAGE_GEN_PROVIDER"] = "mock"

# Throwaway database + upload dir so tests never touch real data.
os.environ["DATABASE_URL"] = os.path.join(_tmp, "test.db")
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
os.environ["LOGIN_ATTEMPTS_PER_HOUR"] = "1000"
os.environ["ALLOW_GUEST_LOGIN"] = "true"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_PUBLISHABLE_KEY"] = ""
