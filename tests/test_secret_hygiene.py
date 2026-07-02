import unittest
from pathlib import Path


class SecretHygieneTest(unittest.TestCase):
    def test_local_environment_files_are_ignored(self):
        ignored = Path(".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env\n", ignored)
        self.assertIn(".env.*", ignored)
        self.assertIn("!.env.example", ignored)

    def test_example_environment_contains_no_key(self):
        example = Path(".env.example").read_text(encoding="utf-8")
        self.assertIn("DEEPSEEK_API_KEY=", example)
        self.assertNotIn("sk-", example)


if __name__ == "__main__":
    unittest.main()
