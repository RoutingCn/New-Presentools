import unittest

from app.ark_html import ArkHtmlProvider
from app.domain import ContentNode, ProjectState
from app.provider_config import ProviderConfig


class FakeTransport:
    def __init__(self, content=None):
        self.calls = []
        self.response = {
            "choices": [
                {
                    "message": {
                        "content": content
                        or "<!doctype html><html><body><main>Ark HTML</main></body></html>"
                    }
                }
            ]
        }

    def __call__(self, url, headers, payload, timeout):
        self.calls.append((url, headers, payload, timeout))
        return self.response


class ArkHtmlProviderTest(unittest.TestCase):
    def test_generates_html_with_ark_chat_completions(self):
        transport = FakeTransport()
        config = ProviderConfig.from_environ({
            "ARK_API_KEY": "ark-secret",
            "ARK_MODEL": "doubao-seed-1-6",
            "ARK_BASE_URL": "https://ark.example.test/api/v3",
            "ARK_TIMEOUT_SECONDS": "22",
        })
        state = ProjectState(
            id="p1",
            title="HTML 演示",
            audience="投资人",
            stage="structure",
        )
        nodes = (
            ContentNode(id="n1", kind="claim", title="主张", body="正文"),
        )

        html = ArkHtmlProvider(config, transport).render(state, nodes)

        self.assertIn("Ark HTML", html)
        url, headers, payload, timeout = transport.calls[0]
        self.assertEqual(url, "https://ark.example.test/api/v3/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer ark-secret")
        self.assertEqual(payload["model"], "doubao-seed-1-6")
        self.assertIn("HTML 演示", payload["messages"][1]["content"])
        self.assertNotIn("response_format", payload)
        self.assertEqual(timeout, 22.0)

    def test_requires_ark_key(self):
        config = ProviderConfig.from_environ({})

        with self.assertRaisesRegex(ValueError, "ARK_API_KEY"):
            ArkHtmlProvider(config)


if __name__ == "__main__":
    unittest.main()
