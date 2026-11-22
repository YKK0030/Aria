import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_core.config import settings
from agent_core.tooling.workspace import Workspace


class WorkspaceTests(unittest.TestCase):
    def test_create_list_read_and_refuse_unapproved_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, "agent_data_dir", directory):
            workspace = Workspace()
            self.assertEqual(workspace.write("Aria_test/index.html", "<h1>Hello</h1>"), "Aria_test/index.html")
            self.assertEqual(workspace.list("Aria_test"), ["index.html"])
            self.assertEqual(workspace.read("Aria_test/index.html"), "<h1>Hello</h1>")
            with self.assertRaises(FileExistsError):
                workspace.write("Aria_test/index.html", "changed")
            workspace.write("Aria_test/index.html", "changed", overwrite=True)
            self.assertEqual(workspace.read("Aria_test/index.html"), "changed")

    def test_rejects_escape_and_external_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, "agent_data_dir", directory):
            workspace = Workspace()
            with self.assertRaises(ValueError):
                workspace.write("../outside.txt", "no")
            external = Path(directory).parent / (Path(directory).name + "-outside")
            external.mkdir()
            try:
                workspace.root.mkdir(parents=True)
                (workspace.root / "escape").symlink_to(external, target_is_directory=True)
                with self.assertRaises(ValueError):
                    workspace.write("escape/file.txt", "no")
            finally:
                external.rmdir()

    def test_active_project_brief_persists_per_chat_without_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, "agent_data_dir", directory):
            workspace = Workspace()
            project = workspace.set_active_project("telegram", "chat-1", "Aria_test", "Build a restaurant landing page.")
            self.assertTrue((workspace.root / "Aria_test").is_dir())
            self.assertEqual(workspace.get_active_project("telegram", "chat-1"), project)
            self.assertIsNone(workspace.get_active_project("telegram", "chat-2"))
            self.assertNotIn("<html", str(project))

    def test_terminal_allows_read_only_workspace_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, "agent_data_dir", directory):
            workspace = Workspace()
            workspace.write("project/notes.txt", "alpha\nbeta TODO\ngamma\n")
            self.assertEqual(workspace.run_command("ls project"), "notes.txt")
            self.assertEqual(workspace.run_command("grep TODO project/notes.txt"), "beta TODO")
            self.assertEqual(workspace.run_command("head -n 2 project/notes.txt"), "alpha\nbeta TODO")
            self.assertEqual(workspace.run_command("wc -l project/notes.txt"), "3")
            self.assertIn("Created directory", workspace.run_command("mkdir project/assets"))
            self.assertIn("Created", workspace.run_command('write project/assets/readme.txt "first line"'))
            self.assertIn("Updated", workspace.run_command('append project/assets/readme.txt " second line"'))
            self.assertEqual(workspace.read("project/assets/readme.txt"), "first line second line")
            with self.assertRaises(FileExistsError):
                workspace.run_command('write project/assets/readme.txt "replacement"')

    def test_terminal_append_cannot_grow_file_past_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, "agent_data_dir", directory):
            workspace = Workspace()
            workspace.write("large.txt", "x" * 250_000)
            with self.assertRaisesRegex(ValueError, "250000 bytes"):
                workspace.run_command('append large.txt "x"')
            self.assertEqual((workspace.root / "large.txt").stat().st_size, 250_000)

    def test_terminal_rejects_shell_and_workspace_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, "agent_data_dir", directory):
            workspace = Workspace()
            for command in ("python -c 'print(1)'", "cat ../secret", "ls; cat notes.txt", "find . -exec id"):
                with self.subTest(command=command), self.assertRaises(ValueError):
                    workspace.run_command(command)


if __name__ == "__main__":
    unittest.main()
