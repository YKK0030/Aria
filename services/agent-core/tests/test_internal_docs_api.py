from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

import httpx

from agent_core.config import settings
from agent_core.internal_docs import internal_docs
from agent_core.main import app


class InternalDocsApiTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addAsyncCleanup(self._cleanup)
        self.root = Path(self.temp.name)
        (self.root / "sop.md").write_text("# Support SOP\n\nRestart the worker and check health.\n", encoding="utf-8")
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
        self.addAsyncCleanup(self.client.aclose)
        self.key_patch = patch.object(settings, "admin_api_key", "test-admin")
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)
        self.docs_patch = patch.object(internal_docs, "root", self.root)
        self.docs_patch.start()
        self.addCleanup(self.docs_patch.stop)
        self.audit_patch = patch("agent_core.main.store.append_audit")
        self.audit_patch.start()
        self.addCleanup(self.audit_patch.stop)
        internal_docs._signature = None

    async def _cleanup(self) -> None:
        internal_docs._signature = None
        self.temp.cleanup()

    async def test_search_and_reindex_require_admin_key(self) -> None:
        denied = await self.client.get("/admin/docs/search", params={"query": "worker health"})
        self.assertEqual(denied.status_code, 401)
        headers = {"x-admin-api-key": "test-admin"}
        indexed = await self.client.post("/admin/docs/reindex", headers=headers)
        self.assertEqual(indexed.json()["files"], 1)
        search = await self.client.get(
            "/admin/docs/search", headers=headers, params={"query": "worker health"}
        )
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["results"][0]["path"], "sop.md")
        self.assertIn("sop.md:L", search.json()["results"][0]["citation"])


if __name__ == "__main__":
    import unittest

    unittest.main()
