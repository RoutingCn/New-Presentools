import json
import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from app.agents import AgentDelivery
from app.deepseek import DeepSeekProvider, UrllibTransport
from app.provider_config import ProviderConfig


def valid_content(role="content"):
    return json.dumps({
        "agent": role,
        "summary": "形成针对当前主题的核心判断。",
        "outputs": [{"kind": "claim", "title": "判断", "body": "正文"}],
        "affected_ids": [],
        "uncertainties": ["需要数据验证"],
        "quality_checks": ["论点明确"],
        "next_action": "验证证据",
    }, ensure_ascii=False)


class FakeTransport:
    def __init__(self, content=None):
        self.response = {"choices": [{"message": {"content": content or valid_content()}}]}
        self.calls = []

    def __call__(self, url, headers, payload, timeout):
        self.calls.append((url, headers, payload, timeout))
        return self.response


class DeepSeekProviderTest(unittest.TestCase):
    def test_returns_valid_agent_delivery(self):
        config = ProviderConfig(
            "test-key", "deepseek-v4-flash", "https://api.deepseek.com", 12
        )
        transport = FakeTransport()

        delivery = DeepSeekProvider(config, transport).run(
            "content",
            {"title": "制造业增长", "audience": "企业决策者"},
            {"events": []},
        )

        self.assertIsInstance(delivery, AgentDelivery)
        self.assertEqual(delivery.agent, "content")
        url, headers, payload, timeout = transport.calls[0]
        self.assertEqual(url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer test-key")
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertIn("制造业增长", payload["messages"][1]["content"])
        self.assertEqual(timeout, 12)

    def provider(self, content):
        config = ProviderConfig(
            "test-key", "deepseek-v4-flash", "https://api.deepseek.com", 12
        )
        return DeepSeekProvider(config, FakeTransport(content))

    def test_rejects_empty_content(self):
        transport = FakeTransport("placeholder")
        transport.response = {"choices": [{"message": {"content": ""}}]}
        config = ProviderConfig(
            "test-key", "deepseek-v4-flash", "https://api.deepseek.com", 12
        )
        with self.assertRaisesRegex(ValueError, "empty content"):
            DeepSeekProvider(config, transport).run("content", {}, {})

    def test_rejects_malformed_json(self):
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            self.provider("not-json").run("content", {}, {})

    def test_rejects_missing_fields(self):
        with self.assertRaisesRegex(ValueError, "missing fields"):
            self.provider(json.dumps({"agent": "content", "summary": "short"})).run(
                "content", {}, {}
            )

    def test_rejects_empty_outputs(self):
        value = json.loads(valid_content())
        value["outputs"] = []
        with self.assertRaisesRegex(ValueError, "non-empty outputs"):
            self.provider(json.dumps(value)).run("content", {}, {})

    def test_rejects_role_mismatch(self):
        with self.assertRaisesRegex(ValueError, "role mismatch"):
            self.provider(valid_content("research")).run("content", {}, {})

    def test_requires_key(self):
        config = ProviderConfig("", "deepseek-v4-flash", "https://api.deepseek.com", 60)
        with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY"):
            DeepSeekProvider(config)


class UrllibTransportTest(unittest.TestCase):
    def test_authentication_error_does_not_expose_response_or_key(self):
        error = HTTPError(
            "https://example.test", 401, "Unauthorized", {},
            io.BytesIO(b"raw-secret-response"),
        )
        with patch("app.deepseek.urlopen", side_effect=error):
            with self.assertRaises(ValueError) as raised:
                UrllibTransport()(
                    "https://example.test",
                    {"Authorization": "Bearer test-key"}, {}, 10,
                )
        message = str(raised.exception)
        self.assertIn("authentication", message)
        self.assertNotIn("test-key", message)
        self.assertNotIn("raw-secret-response", message)

    def test_rate_limit_is_normalized(self):
        error = HTTPError("https://example.test", 429, "limited", {}, None)
        with patch("app.deepseek.urlopen", side_effect=error):
            with self.assertRaisesRegex(ValueError, "rate limit"):
                UrllibTransport()("https://example.test", {}, {}, 10)

    def test_network_error_is_normalized(self):
        with patch("app.deepseek.urlopen", side_effect=URLError("offline")):
            with self.assertRaisesRegex(ValueError, "network unavailable"):
                UrllibTransport()("https://example.test", {}, {}, 10)

    def test_timeout_is_normalized(self):
        with patch("app.deepseek.urlopen", side_effect=TimeoutError()):
            with self.assertRaisesRegex(ValueError, "timed out"):
                UrllibTransport()("https://example.test", {}, {}, 10)


if __name__ == "__main__":
    unittest.main()
