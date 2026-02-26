"""Tests for embedding cache."""

from unittest.mock import patch

import pytest

from app.embedding_cache import _cache_key, get_cached_embedding, set_cached_embedding


class TestCacheKey:
    def test_deterministic(self):
        k1 = _cache_key("test query")
        k2 = _cache_key("test query")
        assert k1 == k2

    def test_different_texts(self):
        k1 = _cache_key("test query one")
        k2 = _cache_key("test query two")
        assert k1 != k2

    def test_includes_model_name(self):
        key = _cache_key("test")
        assert "embed:" in key


class TestGetCachedEmbedding:
    @pytest.mark.asyncio
    async def test_returns_none_on_redis_error(self):
        """Should return None when Redis is unavailable."""
        with patch("app.embedding_cache.settings") as mock_settings:
            mock_settings.redis_url = "redis://nonexistent:9999/0"
            mock_settings.embedding_model = "test-model"
            result = await get_cached_embedding("test query")
            assert result is None


class TestSetCachedEmbedding:
    @pytest.mark.asyncio
    async def test_no_error_on_redis_failure(self):
        """Should fail silently when Redis is unavailable."""
        with patch("app.embedding_cache.settings") as mock_settings:
            mock_settings.redis_url = "redis://nonexistent:9999/0"
            mock_settings.embedding_model = "test-model"
            # Should not raise
            await set_cached_embedding("test query", [0.1, 0.2, 0.3])
