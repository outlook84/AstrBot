from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from astrbot.core.knowledge_base.kb_mgr import KnowledgeBaseManager


class TestKnowledgeBaseManagerInitialize:
    @pytest.mark.asyncio
    async def test_initialize_logs_missing_bm25_dependency_at_startup(self):
        kb_manager = KnowledgeBaseManager(provider_manager=MagicMock())
        kb_manager._init_kb_database = AsyncMock()
        kb_manager.load_kbs = AsyncMock()

        with (
            patch(
                "astrbot.core.knowledge_base.kb_mgr.SparseRetriever.ensure_bm25_dependency_available",
                side_effect=ImportError("No module named 'rank_bm25'"),
            ),
            patch("astrbot.core.knowledge_base.kb_mgr.logger") as mock_logger,
        ):
            await kb_manager.initialize()

        mock_logger.error.assert_called_once()
        mock_logger.warning.assert_called_once()
        kb_manager.load_kbs.assert_not_awaited()
