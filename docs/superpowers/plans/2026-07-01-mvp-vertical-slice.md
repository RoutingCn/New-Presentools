# MVP Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable local workspace that creates a topic project, orchestrates four specialist agents, reviews modification proposals, produces project memory, and locks an immutable artifact.

**Architecture:** A Python standard-library HTTP service owns the domain model, append-only JSON event store, orchestration, and API. A dependency-free HTML/CSS/JavaScript client renders the three-column workspace and calls the API. Agent generation is behind a provider contract; the first provider is deterministic and honest about being local, so a real model can be added without changing versioning or approval logic.

**Tech Stack:** Python 3.12 standard library, SQLite-free JSON event storage, `unittest`, HTML5, CSS, browser JavaScript.

---

## File Map

- `app/domain.py`: project, content node, proposal, artifact, and event types.
- `app/store.py`: append-only event persistence and state projection.
- `app/agents.py`: specialist agent contracts and deterministic provider.
- `app/orchestrator.py`: controller workflow, quality gates, proposals, memory, and locking.
- `app/server.py`: static file server and JSON API.
- `web/index.html`: application shell.
- `web/styles.css`: responsive three-column visual system.
- `web/app.js`: client state, API calls, selection, review, and workflow interactions.
- `tests/test_domain.py`: version and artifact invariants.
- `tests/test_orchestrator.py`: multi-agent workflow and memory.
- `tests/test_server.py`: HTTP contract.
- `tests/test_web_contract.py`: critical UI structure and controls.

### Task 1: Domain Model and Append-Only Store

**Files:**
- Create: `app/__init__.py`
- Create: `app/domain.py`
- Create: `app/store.py`
- Create: `tests/test_domain.py`

- [ ] **Step 1: Write failing tests for event replay and locked artifacts**

```python
def test_replay_builds_project_without_mutating_events(tmp_path):
    store = EventStore(tmp_path)
    project = store.create_project("制造业增长", "企业决策者")
    events = store.events(project.id)
    assert [event.kind for event in events] == ["project.created"]
    assert store.project(project.id).title == "制造业增长"

def test_locked_artifact_is_immutable(tmp_path):
    store = EventStore(tmp_path)
    project = store.create_project("制造业增长", "企业决策者")
    artifact = store.lock_artifact(project.id, "董事会版", ["node-1"])
    with pytest.raises(LockedArtifactError):
        store.replace_locked_artifact(project.id, artifact.id, ["node-2"])
```

- [ ] **Step 2: Run the tests and verify they fail because modules are missing**

Run: `python -m unittest tests.test_domain -v`
Expected: import failure for `app.domain` or `app.store`.

- [ ] **Step 3: Implement serializable dataclasses and append-only JSONL storage**

```python
@dataclass(frozen=True)
class Event:
    id: str
    project_id: str
    kind: str
    at: str
    payload: dict[str, Any]

class EventStore:
    def append(self, project_id: str, kind: str, payload: dict[str, Any]) -> Event:
        event = Event(new_id("evt"), project_id, kind, utc_now(), payload)
        with self.event_path(project_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        return event
```

- [ ] **Step 4: Run domain tests**

Run: `python -m unittest tests.test_domain -v`
Expected: all domain tests pass.

- [ ] **Step 5: Commit**

```bash
git add app tests/test_domain.py
git commit -m "feat: add event-sourced project domain"
```

### Task 2: Agent Contracts and Controller Orchestration

**Files:**
- Create: `app/agents.py`
- Create: `app/orchestrator.py`
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests for four-agent analysis and proposal creation**

```python
def test_topic_analysis_dispatches_all_specialists(tmp_path):
    controller = Controller(EventStore(tmp_path), DeterministicProvider())
    project = controller.create_project("制造业增长", "企业决策者")
    result = controller.analyze_topic(project.id)
    assert set(result.deliveries) == {"content", "research", "visual", "creative"}
    assert result.proposal.status == "pending"

def test_memory_contains_decisions_and_versions(tmp_path):
    controller = Controller(EventStore(tmp_path), DeterministicProvider())
    project = controller.create_project("制造业增长", "企业决策者")
    controller.analyze_topic(project.id)
    memory = controller.memory_markdown(project.id)
    assert "# 项目记忆" in memory
    assert "证据缺口" in memory
```

- [ ] **Step 2: Run tests and verify the controller is missing**

Run: `python -m unittest tests.test_orchestrator -v`
Expected: import failure for `app.orchestrator`.

- [ ] **Step 3: Implement the provider and structured agent delivery contract**

```python
@dataclass(frozen=True)
class AgentDelivery:
    agent: str
    summary: str
    outputs: list[dict[str, Any]]
    affected_ids: list[str]
    uncertainties: list[str]
    quality_checks: list[str]
    next_action: str

class AgentProvider(Protocol):
    def run(self, role: str, contract: dict[str, Any], context: dict[str, Any]) -> AgentDelivery: ...
```

- [ ] **Step 4: Implement controller dispatch, quality checks, proposal creation, and memory projection**

```python
class Controller:
    ROLES = ("content", "research", "visual", "creative")

    def analyze_topic(self, project_id: str) -> AnalysisResult:
        deliveries = {
            role: self.provider.run(role, self.store.project(project_id).contract, self.store.context(project_id))
            for role in self.ROLES
        }
        self._validate(deliveries)
        proposal = self.store.create_proposal(project_id, self._merge(deliveries))
        return AnalysisResult(deliveries, proposal)
```

- [ ] **Step 5: Run orchestration tests and commit**

Run: `python -m unittest tests.test_orchestrator -v`
Expected: all orchestration tests pass.

```bash
git add app/agents.py app/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orchestrate specialist agents"
```

### Task 3: JSON API and Static Server

**Files:**
- Create: `app/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_create_analyze_accept_and_lock(tmp_path):
    app = create_app(tmp_path)
    project = app.handle("POST", "/api/projects", {"title": "制造业增长", "audience": "企业决策者"})
    analysis = app.handle("POST", f"/api/projects/{project['id']}/analyze", {})
    accepted = app.handle("POST", f"/api/projects/{project['id']}/proposals/{analysis['proposal']['id']}/accept", {})
    locked = app.handle("POST", f"/api/projects/{project['id']}/artifacts/lock", {"name": "正式版"})
    assert accepted["status"] == "accepted"
    assert locked["locked"] is True
```

- [ ] **Step 2: Run the test and verify the server module is missing**

Run: `python -m unittest tests.test_server -v`
Expected: import failure for `app.server`.

- [ ] **Step 3: Implement API routing and static serving**

```python
ROUTES = {
    ("POST", "/api/projects"): create_project,
    ("GET", "/api/projects/{project_id}"): get_project,
    ("POST", "/api/projects/{project_id}/analyze"): analyze_topic,
    ("POST", "/api/projects/{project_id}/proposals/{proposal_id}/accept"): accept_proposal,
    ("POST", "/api/projects/{project_id}/artifacts/lock"): lock_artifact,
    ("GET", "/api/projects/{project_id}/memory"): get_memory,
}
```

- [ ] **Step 4: Run API tests and commit**

Run: `python -m unittest tests.test_server -v`
Expected: all API tests pass.

```bash
git add app/server.py tests/test_server.py
git commit -m "feat: expose local workspace API"
```

### Task 4: Interactive Three-Column Workspace

**Files:**
- Create: `web/index.html`
- Create: `web/styles.css`
- Create: `web/app.js`
- Create: `tests/test_web_contract.py`

- [ ] **Step 1: Write failing web contract tests**

```python
def test_workspace_has_stable_regions_and_agent_actions():
    html = Path("web/index.html").read_text(encoding="utf-8")
    assert 'data-region="outline"' in html
    assert 'data-region="workspace"' in html
    assert 'data-region="utility"' in html
    assert 'id="analyze-topic"' in html
    assert 'id="lock-artifact"' in html

def test_styles_use_visible_workspace_dividers():
    css = Path("web/styles.css").read_text(encoding="utf-8")
    assert "--divider-width: 3px" in css
```

- [ ] **Step 2: Run tests and verify missing files**

Run: `python -m unittest tests.test_web_contract -v`
Expected: file-not-found failure for `web/index.html`.

- [ ] **Step 3: Implement the semantic workspace shell**

```html
<div class="workspace-shell">
  <aside data-region="outline"></aside>
  <main data-region="workspace"></main>
  <aside data-region="utility">
    <nav role="tablist" aria-label="协作工具"></nav>
  </aside>
</div>
```

- [ ] **Step 4: Implement client actions and local selection references**

```javascript
async function analyzeTopic() {
  setBusy(true);
  const result = await api.post(`/api/projects/${state.project.id}/analyze`, {});
  state.proposal = result.proposal;
  render();
  setBusy(false);
}
```

- [ ] **Step 5: Run web tests and commit**

Run: `python -m unittest tests.test_web_contract -v`
Expected: all web contract tests pass.

```bash
git add web tests/test_web_contract.py
git commit -m "feat: build agent workspace interface"
```

### Task 5: End-to-End Vertical Slice

**Files:**
- Create: `tests/test_vertical_slice.py`
- Create: `README.md`
- Modify: `app/server.py`
- Modify: `web/app.js`

- [ ] **Step 1: Write the failing full workflow test**

```python
def test_topic_to_locked_artifact_preserves_history(tmp_path):
    controller = Controller(EventStore(tmp_path), DeterministicProvider())
    project = controller.create_project("制造业增长", "企业决策者")
    analysis = controller.analyze_topic(project.id)
    controller.accept_proposal(project.id, analysis.proposal.id)
    artifact = controller.lock_artifact(project.id, "正式版")
    assert artifact.locked
    assert len(controller.events(project.id)) >= 8
    assert artifact.id in controller.memory_markdown(project.id)
```

- [ ] **Step 2: Run and verify the acceptance test fails on the missing history invariant**

Run: `python -m unittest tests.test_vertical_slice -v`
Expected: failure until artifact IDs and all agent dispatches are represented in memory and events.

- [ ] **Step 3: Complete the history projection and add run instructions**

```markdown
## Run

```powershell
python -m app.server --port 4173
```

Open http://127.0.0.1:4173 and choose “从主题开始”.
```

- [ ] **Step 4: Run the complete suite**

Run: `python -m unittest discover -s tests -v`
Expected: all tests pass with zero failures.

- [ ] **Step 5: Browser verification**

Verify at desktop and mobile widths: create a project, run analysis, inspect four deliveries, accept the proposal, open memory, lock the artifact, and confirm the locked state cannot be directly edited.

- [ ] **Step 6: Commit**

```bash
git add README.md app web tests
git commit -m "feat: complete MVP vertical slice"
```
