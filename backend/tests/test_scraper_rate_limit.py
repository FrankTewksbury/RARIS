"""Tests for scraper rate limiting enforcement."""

import time

import pytest

from app.acquisition.scraper import _domain_last_request, _enforce_rate_limit


class TestEnforceRateLimit:
    @pytest.fixture(autouse=True)
    def clear_timestamps(self):
        _domain_last_request.clear()
        yield
        _domain_last_request.clear()

    @pytest.mark.asyncio
    async def test_no_delay_on_first_request(self):
        start = time.monotonic()
        await _enforce_rate_limit("https://example.gov/page", 2000)
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # No delay on first request

    @pytest.mark.asyncio
    async def test_records_domain_timestamp(self):
        await _enforce_rate_limit("https://example.gov/page", 2000)
        assert "example.gov" in _domain_last_request
        assert _domain_last_request["example.gov"] > 0

    @pytest.mark.asyncio
    async def test_different_domains_no_delay(self):
        await _enforce_rate_limit("https://example.gov/a", 2000)
        start = time.monotonic()
        await _enforce_rate_limit("https://other.gov/b", 2000)
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # Different domains — no delay

    @pytest.mark.asyncio
    async def test_same_domain_enforces_delay(self):
        await _enforce_rate_limit("https://example.gov/a", 200)  # 200ms
        start = time.monotonic()
        await _enforce_rate_limit("https://example.gov/b", 200)
        elapsed = time.monotonic() - start
        assert elapsed >= 0.15  # Should wait ~200ms

    @pytest.mark.asyncio
    async def test_zero_rate_limit_no_delay(self):
        start = time.monotonic()
        await _enforce_rate_limit("https://example.gov/a", 0)
        await _enforce_rate_limit("https://example.gov/b", 0)
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # No delay when disabled
