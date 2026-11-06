"""Unit tests for AI Providers and Quota Safety."""
import pytest
from datetime import UTC, datetime
from app.integrations.ai_providers.provider import (
    MockAIProvider,
    OpenRouterAIProvider,
    UnavailableAIProvider,
)
from app.core.config import Settings


@pytest.mark.asyncio
async def test_mock_ai_provider_deterministic():
    provider = MockAIProvider()
    result = await provider.analyse_email(
        message_id="msg-test-1",
        subject="Urgent purchase order for SO-1025",
        sender_address="buyer@company.com",
        body_preprocessed="Please find attached purchase order for SO-1025. Please confirm delivery.",
        sent_at=datetime.now(UTC),
        idempotency_key="test-key-1",
    )

    assert result.success is True
    assert result.analysis is not None
    assert result.analysis.domain == "PURCHASE"
    assert result.analysis.priority == "HIGH"
    assert any(r.value == "SO-1025" for r in result.analysis.references)
    assert len(result.analysis.actions) > 0


@pytest.mark.asyncio
async def test_unavailable_ai_provider():
    provider = UnavailableAIProvider()
    result = await provider.analyse_email(
        message_id="msg-test-2",
        subject="Hello",
        sender_address="user@company.com",
        body_preprocessed="Test",
        sent_at=None,
        idempotency_key="test-key-2",
    )

    assert result.success is False
    assert result.error_class == "PROVIDER_UNAVAILABLE"


def test_openrouter_quota_checker_enforces_limit():
    settings = Settings(
        ai_provider="openrouter",
        openrouter_api_key="fake-key",
        openrouter_model="test-model",
        openrouter_max_requests_per_day=2,
    )
    provider = OpenRouterAIProvider(settings)

    # Initial check passes
    assert provider._check_quota() is None

    # Simulate 2 requests
    provider._record_request()
    provider._record_request()

    # Third request must be blocked by quota limit
    quota_err = provider._check_quota()
    assert quota_err is not None
    assert "Daily quota of 2 requests exhausted" in quota_err
