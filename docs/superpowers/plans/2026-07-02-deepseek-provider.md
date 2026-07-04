# DeepSeek Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make topic analysis use real DeepSeek responses when a server-side key is configured, while preserving clearly labeled deterministic fallback behavior.

**Architecture:** Add an immutable environment configuration and a dependency-injected `DeepSeekProvider` behind the existing `AgentProvider` protocol. Select the provider once during server startup, expose only safe provider metadata through health, and leave orchestration, event storage, approvals, memory, and locking unchanged.

**Tech Stack:** Python 3 standard library (`dataclasses`, `json`, `urllib.request`, `urllib.error`), `unittest`, vanilla HTML/CSS/JavaScript.

---

## File Map

- Create `app/provider_config.py`: parse and validate provider environment settings.
- Create `app/deepseek.py`: construct DeepSeek requests, execute HTTPS calls, validate JSON, and return `AgentDelivery`.
- Create `tests/test_provider_config.py`: configuration and fallback contract tests.
- Create `tests/test_deepseek_provider.py`: request, response, and error contract tests with a fake transport.
- Modify `app/server.py`: provider selection, safe health metadata, and test injection points.
- Modify `tests/test_server.py`: DeepSeek selection, fallback, and secret non-disclosure tests.
- Modify `web/index.html`: give the provider badge a stable identifier.
- Modify `web/app.js`: load and render provider health status.
- Modify `tests/test_web_contract.py`: verify dynamic provider status is wired.
- Modify `.gitignore`: exclude local environment files.
- Create `.env.example`: document non-secret variable names and defaults.
- Modify `README.md`: document safe PowerShell startup and fallback behavior.

### Task 1: Environment Configuration

**Files:**
- Create: `app/provider_config.py`
- Create: `tests/test_provider_config.py`

- [ ] **Step 1: Write failing configuration tests**

```python
import unittest

from app.provider_config import ProviderConfig


class ProviderConfigTest(unittest.TestCase):
    def test_defaults_to_local_provider_without_key(self):
        config = ProviderConfig.from_environ({})
        self.assertFalse(config.deepseek_enabled)
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

    def test_rejects_non_positive_timeout(self):
        with self.assertRaisesRegex(ValueError, "DEEPSEEK_TIMEOUT_SECONDS"):
            ProviderConfig.from_environ({"DEEPSEEK_TIMEOUT_SECONDS": "0"})
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m unittest tests.test_provider_config -v`

Expected: import failure because `app.provider_config` does not exist.

- [ ] **Step 3: Implement the immutable configuration**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ProviderConfig:
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float

    @property
    def deepseek_enabled(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> "ProviderConfig":
        raw_timeout = environ.get("DEEPSEEK_TIMEOUT_SECONDS", "60").strip()
        try:
            timeout = float(raw_timeout)
        except ValueError as error:
            raise ValueError("DEEPSEEK_TIMEOUT_SECONDS must be a positive number") from error
        if timeout <= 0:
            raise ValueError("DEEPSEEK_TIMEOUT_SECONDS must be a positive number")
        return cls(
            api_key=environ.get("DEEPSEEK_API_KEY", "").strip(),
            model=environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash").strip() or "deepseek-v4-flash",
            base_url=(environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip() or "https://api.deepseek.com").rstrip("/"),
            timeout_seconds=timeout,
        )
```

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `python -m unittest tests.test_provider_config -v`

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/provider_config.py tests/test_provider_config.py
git commit -m "feat: add provider environment configuration"
```

### Task 2: DeepSeek Provider Contract

**Files:**
- Create: `app/deepseek.py`
- Create: `tests/test_deepseek_provider.py`

- [ ] **Step 1: Write a failing successful-response test**

Create a `FakeTransport` callable that records `url`, `headers`, `payload`, and `timeout`, then returns this API payload:

```python
{
    "choices": [{
        "message": {"content": json.dumps({
            "agent": "content",
            "summary": "形成针对当前主题的核心判断。",
            "outputs": [{"kind": "claim", "title": "判断", "body": "正文"}],
            "affected_ids": [],
            "uncertainties": ["需要数据验证"],
            "quality_checks": ["论点明确"],
            "next_action": "验证证据"
        }, ensure_ascii=False)}
    }]
}
```

Assert that `DeepSeekProvider(config, transport).run("content", contract, context)` returns an `AgentDelivery`, posts to `https://api.deepseek.com/chat/completions`, sends `Authorization: Bearer test-key`, selects `deepseek-v4-flash`, enables `response_format.type == "json_object"`, and includes the topic in the user message.

- [ ] **Step 2: Run the successful-response test and verify RED**

Run: `python -m unittest tests.test_deepseek_provider.DeepSeekProviderTest.test_returns_valid_agent_delivery -v`

Expected: import failure because `app.deepseek` does not exist.

- [ ] **Step 3: Implement request construction and delivery parsing**

Implement:

```python
class DeepSeekProvider:
    def __init__(self, config: ProviderConfig, transport: HttpTransport | None = None):
        if not config.deepseek_enabled:
            raise ValueError("DeepSeek provider requires DEEPSEEK_API_KEY")
        self.config = config
        self.transport = transport or UrllibTransport()

    def run(self, role: str, contract: dict[str, Any], context: dict[str, Any]) -> AgentDelivery:
        if role not in ROLE_INSTRUCTIONS:
            raise KeyError(f"Unknown agent role: {role}")
        response = self.transport(
            f"{self.config.base_url}/chat/completions",
            {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"},
            {
                "model": self.config.model,
                "messages": build_messages(role, contract, context),
                "response_format": {"type": "json_object"},
                "max_tokens": 3000,
            },
            self.config.timeout_seconds,
        )
        return parse_delivery(role, response)
```

Define focused Chinese `ROLE_INSTRUCTIONS` for content, research, visual, and creative roles. `build_messages` must explicitly request JSON and include one complete `AgentDelivery` example. `parse_delivery` must require all seven delivery fields, require `outputs` to be a non-empty list, convert list fields to tuples, and reject an `agent` value that differs from the requested role.

Implement `UrllibTransport.__call__` with `urllib.request.Request`, UTF-8 JSON encoding, `urlopen(..., timeout=timeout)`, and UTF-8 JSON decoding.

- [ ] **Step 4: Run the successful-response test and verify GREEN**

Run: `python -m unittest tests.test_deepseek_provider.DeepSeekProviderTest.test_returns_valid_agent_delivery -v`

Expected: 1 test passes.

- [ ] **Step 5: Add failing provider error tests**

Add separate tests asserting concise `ValueError` messages for empty `choices[0].message.content`, malformed assistant JSON, missing `quality_checks`, empty `outputs`, and role mismatch. Add transport tests that translate `HTTPError(401)`, `HTTPError(429)`, `URLError`, and `TimeoutError` into messages that contain no API key and no raw response body.

- [ ] **Step 6: Run error tests and verify RED**

Run: `python -m unittest tests.test_deepseek_provider -v`

Expected: the newly added error tests fail because normalization is incomplete.

- [ ] **Step 7: Implement minimal error normalization**

Catch network exceptions inside `UrllibTransport` and raise messages using only status categories: authentication failed, rate limited, request failed with status code, timed out, or network unavailable. In `parse_delivery`, raise `ValueError("DeepSeek returned ...")` messages without embedding raw content.

- [ ] **Step 8: Run provider tests and verify GREEN**

Run: `python -m unittest tests.test_deepseek_provider -v`

Expected: all provider tests pass without network access.

- [ ] **Step 9: Commit**

```bash
git add app/deepseek.py tests/test_deepseek_provider.py
git commit -m "feat: add DeepSeek agent provider"
```

### Task 3: Server Provider Selection and Safe Health Status

**Files:**
- Modify: `app/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write failing server selection tests**

Add tests that call `create_app(temp_path, environ={})` and expect health to return `{"status": "ok", "provider": "deterministic-local"}`. Add a second test with `DEEPSEEK_API_KEY: "server-secret"` and an injected fake transport, expecting `provider == "deepseek"`, `model == "deepseek-v4-flash"`, and asserting `"server-secret" not in json.dumps(health)`.

- [ ] **Step 2: Run selection tests and verify RED**

Run: `python -m unittest tests.test_server -v`

Expected: failure because `create_app` does not accept `environ` or `transport` and health is fixed.

- [ ] **Step 3: Implement provider selection**

Change the factory signature to:

```python
def create_app(
    data_root: Path,
    environ: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
) -> ApiApplication:
    config = ProviderConfig.from_environ(os.environ if environ is None else environ)
    if config.deepseek_enabled:
        provider = DeepSeekProvider(config, transport)
        provider_info = {"provider": "deepseek", "model": config.model}
    else:
        provider = DeterministicProvider()
        provider_info = {"provider": "deterministic-local"}
    return ApiApplication(Controller(EventStore(Path(data_root)), provider), provider_info)
```

Store a copy of `provider_info` on `ApiApplication` and merge it into the health response. Do not store `ProviderConfig` on the API application.

- [ ] **Step 4: Run server tests and verify GREEN**

Run: `python -m unittest tests.test_server -v`

Expected: all server tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/server.py tests/test_server.py
git commit -m "feat: select model provider at server startup"
```

### Task 4: Dynamic Provider Badge

**Files:**
- Modify: `web/index.html`
- Modify: `web/app.js`
- Modify: `tests/test_web_contract.py`

- [ ] **Step 1: Write a failing web contract test**

Assert that `web/index.html` contains `id="provider-status"` and that `web/app.js` calls `/api/health`, maps `deepseek` to a label containing the returned model, and maps fallback to `本地模拟`.

- [ ] **Step 2: Run the web contract test and verify RED**

Run: `python -m unittest tests.test_web_contract -v`

Expected: failure because the badge is static and the health endpoint is not called.

- [ ] **Step 3: Implement health rendering**

Give the existing badge `id="provider-status"`. Add:

```javascript
async function loadProviderStatus(){
  const badge=$("#provider-status");
  try{
    const health=await api.get("/api/health");
    badge.lastChild.textContent=health.provider==="deepseek"
      ? ` DeepSeek · ${health.model}`
      : " 本地模拟";
  }catch(error){
    badge.lastChild.textContent=" Provider 状态未知";
  }
}

loadProviderStatus();
```

Keep the existing status dot and do not expose configuration details beyond provider and model.

- [ ] **Step 4: Run web tests and verify GREEN**

Run: `python -m unittest tests.test_web_contract -v`

Expected: all web contract tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/index.html web/app.js tests/test_web_contract.py
git commit -m "feat: show active model provider"
```

### Task 5: Secret Hygiene, Documentation, and Full Verification

**Files:**
- Modify: `.gitignore`
- Create: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Write a failing secret-hygiene test**

Add a web or configuration contract test that requires `.gitignore` entries for `.env` and `.env.*`, with an exception for `.env.example`, and verifies `.env.example` contains no value beginning with `sk-`.

- [ ] **Step 2: Run the hygiene test and verify RED**

Run: `python -m unittest discover -s tests -v`

Expected: failure because environment files are not yet covered.

- [ ] **Step 3: Add safe configuration examples and startup instructions**

Append to `.gitignore`:

```gitignore
.env
.env.*
!.env.example
```

Create `.env.example`:

```dotenv
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_TIMEOUT_SECONDS=60
```

Document that the pasted key must be revoked. Show PowerShell setup with a neutral placeholder, then the existing server command. State that no key means clearly labeled local simulation and that the application does not automatically read `.env` files.

- [ ] **Step 4: Run the full automated suite and verify GREEN**

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass with no network calls, warnings, or secrets in output.

- [ ] **Step 5: Restart the local server without a key and verify fallback**

Run the server on an unused port with no `DEEPSEEK_API_KEY`, open the workspace, and verify the badge reads `本地模拟`, topic analysis still completes, and browser console contains no errors.

- [ ] **Step 6: Configure a newly generated key and run one live check**

After the user has revoked the exposed key and configured a new key in the local PowerShell process, restart the server. Verify `/api/health` reports DeepSeek and the selected model, submit a distinctive topic, and confirm all four deliveries are topic-specific. Inspect project events and memory to confirm no key or authorization header is persisted.

- [ ] **Step 7: Commit**

```bash
git add .gitignore .env.example README.md tests
git commit -m "docs: add safe DeepSeek setup and verification"
```

### Task 6: Final Review

**Files:**
- Review all changed files.

- [ ] **Step 1: Inspect the diff for secret leakage**

Run: `git diff HEAD~5 -- . ':!.worktrees'`

Expected: no real API key, authorization value, raw API response, or generated project data.

- [ ] **Step 2: Run final verification**

Run: `python -m unittest discover -s tests -v`

Expected: complete suite passes.

- [ ] **Step 3: Confirm working tree scope**

Run: `git status --short`

Expected: only intentional DeepSeek integration changes, or a clean tree after commits.
