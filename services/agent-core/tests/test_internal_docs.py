from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from agent_core.internal_docs import InternalDocsIndex
from agent_core.models import InboundEvent
from agent_core.runtime import AgentRuntime


class InternalDocsIndexTests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "operations").mkdir()
        (self.root / "operations" / "deploy.md").write_text(
            "# Deployment SOP\n\nUse the staging approval gate before production deployment.\n"
            "Confirm the rollback plan and check the health endpoint.\n",
            encoding="utf-8",
        )
        (self.root / "unrelated.txt").write_text("South Indian dosa menu and coffee.", encoding="utf-8")
        (self.root / "ignored.py").write_text("deployment staging approval", encoding="utf-8")
        self.index = InternalDocsIndex(self.root)

    def test_search_returns_relevant_excerpt_with_file_and_line_citation(self) -> None:
        results = self.index.search("production deployment staging approval")
        self.assertTrue(results)
        result = results[0]
        self.assertEqual(result["path"], "operations/deploy.md")
        self.assertEqual(result["title"], "Deployment SOP")
        self.assertRegex(result["citation"], r"\[operations/deploy\.md:L\d+-L\d+\]")
        self.assertIn("rollback plan", result["snippet"])

    def test_search_skips_non_docs_and_returns_empty_when_no_terms_match(self) -> None:
        self.assertEqual(self.index.search("quantum satellite"), [])
        self.assertNotIn("ignored.py", {item["path"] for item in self.index.search("deployment staging approval")})

    def test_reindex_reports_files_and_refreshes_changed_content(self) -> None:
        self.assertEqual(self.index.reindex(), {"files": 2, "chunks": 2})
        file = self.root / "operations" / "deploy.md"
        file.write_text("# New SOP\n\nRotate the webhook secret quarterly.\n", encoding="utf-8")
        self.assertEqual(self.index.search("webhook secret")[0]["title"], "New SOP")

    def test_symlinked_document_is_not_read(self) -> None:
        outside = self.root.parent / f"{self.root.name}-external.md"
        outside.write_text("private deployment secret", encoding="utf-8")
        self.addCleanup(outside.unlink)
        (self.root / "external.md").symlink_to(outside)
        paths = {item["path"] for item in self.index.search("private deployment secret")}
        self.assertNotIn("external.md", paths)


class InternalDocsToolTests(IsolatedAsyncioTestCase):
    async def test_agent_exposes_docs_search_and_returns_citations(self) -> None:
        event = InboundEvent(
            channel="telegram", chatId="123", senderId="123", messageId="m1",
            text="what is our deployment procedure", timestamp=1,
        )
        tools = {item.name: item for item in AgentRuntime()._tools_for(event, [])}
        self.assertIn("search_internal_docs", tools)
        cited = [{"citation": "[operations/deploy.md:L1-L4]", "snippet": "staging approval"}]
        with (
            patch("agent_core.runtime.internal_docs.search", return_value=cited),
            patch("agent_core.runtime.store.append_audit") as audit,
        ):
            result = tools["search_internal_docs"].entrypoint(query="deployment SOP")
        self.assertIn("operations/deploy.md", result)
        audit.assert_called_once_with("internal_docs_searched", {
            "channel": "telegram", "chat_id": "123", "result_count": 1,
        })
