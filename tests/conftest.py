"""Make the test suite hermetic: force the offline (no-API) code paths so tests
are deterministic and never hit the network, regardless of the developer's
ambient environment.
"""
import pytest

from autoflow import net

_OFFLINE_ENV = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    # Without these a developer with a real webhook exported would have the
    # test suite post to their live Slack channel.
    "AUTOFLOW_WEBHOOK_URL",
    "AUTOFLOW_ERROR_WEBHOOK_URL",
    # Ambient tuning must not change assertions about defaults.
    "AUTOFLOW_LLM_TIMEOUT",
    "AUTOFLOW_LLM_RETRIES",
    "AUTOFLOW_LLM_MAX_TOKENS",
    "AUTOFLOW_LLM_TOKEN_BUDGET",
    "AUTOFLOW_LOG_LEVEL",
    "AUTOFLOW_LOG_FORMAT",
    # Delivery credentials: a stray export must never reach a real inbox or chat.
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "SMTP_HOST",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
)


@pytest.fixture(autouse=True)
def _force_offline(monkeypatch):
    for name in _OFFLINE_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Retry backoff must never actually slow the suite down."""
    monkeypatch.setattr(net.time, "sleep", lambda _seconds: None)
