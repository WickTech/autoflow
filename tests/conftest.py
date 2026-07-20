"""Make the test suite hermetic: force the offline (no-API) code paths so tests
are deterministic and never hit the network, regardless of the developer's
ambient environment.
"""
import pytest

from autoflow import net

_OFFLINE_ENV = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    # Without these a developer with a real webhook exported would have the
    # test suite post to their live Slack channel.
    "AUTOFLOW_WEBHOOK_URL",
    "AUTOFLOW_ERROR_WEBHOOK_URL",
)


@pytest.fixture(autouse=True)
def _force_offline(monkeypatch):
    for name in _OFFLINE_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Retry backoff must never actually slow the suite down."""
    monkeypatch.setattr(net.time, "sleep", lambda _seconds: None)
