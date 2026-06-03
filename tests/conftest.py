"""Make the test suite hermetic: force the offline (no-API) code paths so tests
are deterministic and never hit the network, regardless of the developer's
ambient environment.
"""
import pytest


@pytest.fixture(autouse=True)
def _force_offline(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
