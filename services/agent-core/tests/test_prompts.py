import unittest

from agent_core.prompts import build_system_prompt, select_task_prompt


class PromptLibraryTests(unittest.TestCase):
    def test_selects_task_prompt_from_current_request(self):
        self.assertEqual(select_task_prompt("Search the web for today's news"), "research")
        self.assertEqual(select_task_prompt("create a tool to add integers"), "tool_creation")
        self.assertEqual(select_task_prompt("debug this Python traceback"), "coding")
        self.assertEqual(select_task_prompt("Create a South Indian restaurant HTML page"), "coding")
        self.assertEqual(select_task_prompt("draft an email"), "writing")
        self.assertEqual(select_task_prompt("Explain safe ROS2 robot arm motion planning"), "robotics")
        self.assertEqual(select_task_prompt("hello there"), "general")

    def test_builds_task_specific_system_prompt(self):
        research = build_system_prompt("Search for current Ollama news")
        general = build_system_prompt("hello")
        self.assertIn("source URLs", research)
        self.assertNotIn("source URLs", general)


if __name__ == "__main__":
    unittest.main()
