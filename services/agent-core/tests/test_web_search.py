import unittest
from unittest.mock import patch

from tools import web_search


class WebSearchTests(unittest.TestCase):
    def test_rejects_private_hosts(self):
        for url in ("http://127.0.0.1/", "http://192.168.1.1/", "http://localhost/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                web_search._validate_public_url(url)

    def test_rejects_domain_resolving_to_private_address(self):
        with patch.object(web_search.socket, "getaddrinfo", return_value=[(0, 0, 0, "", ("10.0.0.4", 80))]):
            with self.assertRaisesRegex(ValueError, "private"):
                web_search._validate_public_url("https://example.com/")

    def test_resolves_duckduckgo_result_and_limits_result_count(self):
        markup = (
            '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2F">'
            "Example</a>"
        )
        with patch.object(web_search, "_get", return_value=("", "text/html", markup.encode())) as get:
            result = web_search.run(query="test", limit=99)
        self.assertIn("Example — https://example.org/", result)
        self.assertIn("q=test", get.call_args.args[0])

    def test_page_fetch_strips_script_content_and_caps_output(self):
        html = b"<h1>Public</h1><script>secret()</script><p>Useful text</p>"
        with patch.object(web_search, "_get", return_value=("https://example.org", "text/html", html)):
            result = web_search.run(url="https://example.org")
        self.assertIn("Useful text", result)
        self.assertNotIn("secret()", result)


if __name__ == "__main__":
    unittest.main()
