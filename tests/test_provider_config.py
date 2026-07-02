import unittest

from app.provider_config import ProviderConfig


class ProviderConfigTest(unittest.TestCase):
    def test_defaults_to_local_provider_without_key(self):
        config = ProviderConfig.from_environ({})
        self.assertFalse(config.deepseek_enabled)
        self.assertFalse(config.require_deepseek)
        self.assertEqual(config.model, "deepseek-v4-flash")
        self.assertEqual(config.base_url, "https://api.deepseek.com")
        self.assertEqual(config.timeout_seconds, 60.0)

    def test_reads_trimmed_deepseek_settings(self):
        config = ProviderConfig.from_environ({
            "DEEPSEEK_API_KEY": "  secret-value  ",
            "DEEPSEEK_MODEL": "deepseek-v4-pro",
            "DEEPSEEK_BASE_URL": "https://example.test/",
            "DEEPSEEK_TIMEOUT_SECONDS": "12.5",
        })
        self.assertTrue(config.deepseek_enabled)
        self.assertEqual(config.api_key, "secret-value")
        self.assertEqual(config.model, "deepseek-v4-pro")
        self.assertEqual(config.base_url, "https://example.test")
        self.assertEqual(config.timeout_seconds, 12.5)

    def test_reads_required_deepseek_flag(self):
        config = ProviderConfig.from_environ({"REQUIRE_DEEPSEEK": "1"})

        self.assertTrue(config.require_deepseek)

    def test_reads_trimmed_ark_html_settings(self):
        config = ProviderConfig.from_environ({
            "ARK_API_KEY": "  ark-secret  ",
            "ARK_MODEL": "doubao-seed-1-6",
            "ARK_BASE_URL": "https://ark.example.test/api/v3/",
            "ARK_TIMEOUT_SECONDS": "30",
            "REQUIRE_ARK_HTML": "yes",
        })

        self.assertTrue(config.ark_html_enabled)
        self.assertTrue(config.require_ark_html)
        self.assertEqual(config.ark_api_key, "ark-secret")
        self.assertEqual(config.ark_model, "doubao-seed-1-6")
        self.assertEqual(config.ark_base_url, "https://ark.example.test/api/v3")
        self.assertEqual(config.ark_timeout_seconds, 30.0)

    def test_rejects_non_positive_timeout(self):
        with self.assertRaisesRegex(ValueError, "DEEPSEEK_TIMEOUT_SECONDS"):
            ProviderConfig.from_environ({"DEEPSEEK_TIMEOUT_SECONDS": "0"})

    def test_rejects_non_numeric_timeout(self):
        with self.assertRaisesRegex(ValueError, "DEEPSEEK_TIMEOUT_SECONDS"):
            ProviderConfig.from_environ({"DEEPSEEK_TIMEOUT_SECONDS": "slow"})


if __name__ == "__main__":
    unittest.main()
