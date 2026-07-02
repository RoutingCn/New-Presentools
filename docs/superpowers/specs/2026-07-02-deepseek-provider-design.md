# DeepSeek Provider Integration Design

## Goal

Replace simulated topic analysis with real DeepSeek calls while keeping the deterministic provider for offline development and tests. This iteration covers the four existing specialist agents only. Internet and local-directory research remain follow-up work.

## Decisions

- Keep the existing `AgentProvider` boundary so orchestration remains provider-independent.
- Use DeepSeek when `DEEPSEEK_API_KEY` is present; otherwise use `DeterministicProvider`.
- Default every specialist agent to `deepseek-v4-flash` for the MVP.
- Allow `DEEPSEEK_MODEL` to override the model. Per-role routing is deferred.
- Credentials remain server-side and must never enter browser responses, logs, project events, or `memory.md`.
- The key pasted into chat is compromised and must be revoked. The application must not use it.

## Configuration

An immutable startup configuration reads:

- `DEEPSEEK_API_KEY`: enables the real provider when non-empty.
- `DEEPSEEK_MODEL`: defaults to `deepseek-v4-flash`.
- `DEEPSEEK_BASE_URL`: defaults to `https://api.deepseek.com`.
- `DEEPSEEK_TIMEOUT_SECONDS`: defaults to 60 and must be positive.

Configuration is read once when the server starts. This iteration does not add a secret-setting UI or project-level credentials.

## DeepSeek Provider

`DeepSeekProvider` implements the synchronous `AgentProvider.run(role, contract, context)` protocol. It uses Python standard-library HTTPS support, preserving the dependency-free server.

Each request includes a role-specific professional instruction, the task contract, relevant project context, and an explicit JSON example matching `AgentDelivery`. JSON output mode and a bounded token limit are enabled. The provider validates the HTTP response, parses assistant content, and constructs an `AgentDelivery`. The controller's current quality validation remains the second validation layer.

## Provider Status

`create_app` selects the provider from environment configuration. The health endpoint returns safe metadata only:

```json
{
  "status": "ok",
  "provider": "deepseek",
  "model": "deepseek-v4-flash"
}
```

Without a key it reports `deterministic-local`. The web workspace uses this response for its provider label so simulation cannot be mistaken for real analysis.

## Data Flow

1. The browser submits a topic and starts analysis through the existing API.
2. The controller calls the provider for content, research, visual, and creative roles.
3. DeepSeek receives only the role prompt, project contract, and relevant project context.
4. Each valid response becomes an `AgentDelivery` and is appended to the event store.
5. After all four deliveries pass validation, the controller creates the existing reviewable proposal.
6. Approval, full-content output, memory projection, and locking continue unchanged.

No partial proposal is created. If a later role fails, earlier completed deliveries may remain as process events, but the UI reports failure and does not present the run as complete. A manual retry starts another analysis run.

## Errors

The provider returns concise application errors for invalid credentials, quota or rate limits, other HTTP failures, timeouts, network failures, empty content, malformed JSON, missing fields, and role mismatch. Errors must not contain authorization data, the full request payload, or raw response bodies.

Automatic retries are deferred because they affect cost and duplicate-event semantics. The user can explicitly retry analysis.

## Testing

Implementation follows test-driven development:

- Configuration tests cover DeepSeek selection, local fallback, defaults, and invalid timeout values.
- Provider tests use a fake HTTP transport to verify request structure and `AgentDelivery` conversion without API cost.
- Failure tests cover HTTP errors, timeout, empty content, malformed JSON, missing fields, and role mismatch.
- Server tests verify safe health metadata and confirm secrets never appear in responses.
- Existing domain, orchestration, locking, memory, and web-contract tests remain green.
- One manually authorized live connectivity check runs only after a newly generated key is configured locally.

## Security and Setup

The repository will contain an example environment file with variable names but no values. `.gitignore` will cover local environment files before any key is configured. Startup documentation will show how to set `DEEPSEEK_API_KEY` in a PowerShell process without placing it in source files, browser storage, project data, or chat.

## Out of Scope

- Internet search and citations.
- Search over a selected local directory.
- Per-agent model routing and provider failover.
- Streaming, cancellation, background jobs, automatic retries, and cost dashboards.
- The manuscript/article entry path.

## Success Criteria

- A valid local key produces four topic-specific deliveries and a reviewable proposal.
- Without a key, the application remains usable in clearly labeled simulation mode.
- No credential appears in the browser, event store, memory, logs, or repository.
- Provider failures are visible and cannot be mistaken for completed analysis.
- Automated tests pass without network access or API credit.
