from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
from dataclasses import asdict, replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from .agents import DeterministicProvider
from .aesthetic_html import AestheticHtmlProvider
from .deepseek import DeepSeekProvider, HttpTransport
from .domain import ContentNode, ProjectState
from .html_provider import LocalHtmlProvider
from .orchestrator import Controller
from .provider_config import ProviderConfig
from .store import EventStore


class ApiApplication:
    def __init__(
        self,
        controller: Controller,
        provider_info: dict[str, str] | None = None,
        config: ProviderConfig | None = None,
        transport: HttpTransport | None = None,
    ):
        self.controller = controller
        self.provider_info = provider_info or {"provider": "deterministic-local"}
        self.config = config or ProviderConfig.from_environ({})
        self.transport = transport

    def handle(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = body or {}
        if method == "GET" and path == "/api/health":
            return {"status": "ok", **self.provider_info}
        if method == "GET" and path == "/api/html-provider":
            return self._html_provider_summary()
        if method == "POST" and path == "/api/html-provider":
            return self._configure_html_provider(body)
        if method == "POST" and path == "/api/html-provider/test":
            return self._test_html_provider()
        if method == "POST" and path == "/api/projects":
            title = str(body.get("title", "")).strip()
            audience = str(body.get("audience", "")).strip()
            if not title:
                raise ValueError("项目主题不能为空")
            if not audience:
                raise ValueError("目标受众不能为空")
            return self.controller.create_project(title, audience).to_dict()

        match = re.fullmatch(r"/api/projects/([^/]+)", path)
        if method == "GET" and match:
            return self.controller.store.project(match.group(1)).to_dict()

        match = re.fullmatch(r"/api/projects/([^/]+)/analyze", path)
        if method == "POST" and match:
            return self.controller.analyze_topic(match.group(1)).to_dict()

        match = re.fullmatch(r"/api/projects/([^/]+)/script", path)
        if method == "POST" and match:
            proposal = self.controller.generate_script(match.group(1))
            return {
                **proposal.__dict__,
                "changes": list(proposal.changes),
                "affected_ids": list(proposal.affected_ids),
            }

        match = re.fullmatch(r"/api/projects/([^/]+)/comments", path)
        if method == "POST" and match:
            proposal = self.controller.submit_comment(
                match.group(1),
                str(body.get("text", "")),
                body.get("target_id"),
            )
            return {
                **proposal.__dict__,
                "changes": list(proposal.changes),
                "affected_ids": list(proposal.affected_ids),
            }

        match = re.fullmatch(r"/api/projects/([^/]+)/nodes/([^/]+)/revision", path)
        if method == "POST" and match:
            proposal = self.controller.revise_node(
                match.group(1),
                match.group(2),
                str(body.get("title", "")),
                str(body.get("body", "")),
            )
            return {
                **proposal.__dict__,
                "changes": list(proposal.changes),
                "affected_ids": list(proposal.affected_ids),
            }

        match = re.fullmatch(r"/api/projects/([^/]+)/nodes/([^/]+)/delete", path)
        if method == "POST" and match:
            proposal = self.controller.delete_node(
                match.group(1),
                match.group(2),
                str(body.get("reason", "")),
            )
            return {
                **proposal.__dict__,
                "changes": list(proposal.changes),
                "affected_ids": list(proposal.affected_ids),
            }

        match = re.fullmatch(
            r"/api/projects/([^/]+)/proposals/([^/]+)/accept",
            path,
        )
        if method == "POST" and match:
            proposal = self.controller.accept_proposal(match.group(1), match.group(2))
            return {
                **proposal.__dict__,
                "changes": list(proposal.changes),
                "affected_ids": list(proposal.affected_ids),
            }

        match = re.fullmatch(
            r"/api/projects/([^/]+)/proposals/([^/]+)/reject",
            path,
        )
        if method == "POST" and match:
            proposal = self.controller.reject_proposal(match.group(1), match.group(2))
            return {
                **proposal.__dict__,
                "changes": list(proposal.changes),
                "affected_ids": list(proposal.affected_ids),
            }

        match = re.fullmatch(r"/api/projects/([^/]+)/artifacts/lock", path)
        if method == "POST" and match:
            name = str(body.get("name", "正式版")).strip() or "正式版"
            artifact = self.controller.lock_artifact(match.group(1), name)
            return {
                **asdict(artifact),
                "node_ids": list(artifact.node_ids),
            }

        match = re.fullmatch(r"/api/projects/([^/]+)/html/preview", path)
        if method == "POST" and match:
            artifact = self.controller.preview_html(
                match.group(1),
                str(body.get("name", "HTML preview")).strip() or "HTML preview",
            )
            return {
                **asdict(artifact),
                "node_ids": list(artifact.node_ids),
            }

        match = re.fullmatch(r"/api/projects/([^/]+)/html/([^/]+)/lock", path)
        if method == "POST" and match:
            artifact = self.controller.lock_html_preview(match.group(1), match.group(2))
            return {
                **asdict(artifact),
                "node_ids": list(artifact.node_ids),
            }

        match = re.fullmatch(r"/api/projects/([^/]+)/memory", path)
        if method == "GET" and match:
            return {"markdown": self.controller.memory_markdown(match.group(1))}

        raise KeyError(f"Route not found: {method} {path}")

    def _html_provider_summary(self) -> dict[str, Any]:
        if self.provider_info.get("html_provider") == "aesthetic-markdown":
            return {
                "provider": "aesthetic-markdown",
                "model": self.provider_info.get("html_model", "swiss"),
                "base_url": "",
                "key_configured": False,
                "require_remote": False,
            }
        return {
            "provider": "local-template",
            "model": "",
            "base_url": "",
            "key_configured": False,
            "require_remote": False,
        }

    def _configure_html_provider(self, body: dict[str, Any]) -> dict[str, Any]:
        provider = str(body.get("provider", "local-template")).strip()
        if provider in {"aesthetic", "aesthetic-markdown"}:
            paradigm = str(body.get("model", "swiss")).strip() or "swiss"
            self.controller.html_provider = AestheticHtmlProvider(paradigm)
            self.provider_info["html_provider"] = "aesthetic-markdown"
            self.provider_info["html_model"] = paradigm
            return self._html_provider_summary()
        if provider in {"local", "local-template"}:
            self.config = replace(
                self.config,
            )
            self.controller.html_provider = LocalHtmlProvider()
            self.provider_info["html_provider"] = "local-template"
            self.provider_info.pop("html_model", None)
            return self._html_provider_summary()
        raise ValueError(f"Unsupported HTML provider: {provider}")

    def _test_html_provider(self) -> dict[str, Any]:
        state = ProjectState(id="provider-test", title="HTML provider test", audience="tester")
        node = ContentNode(
            id="node-provider-test",
            kind="claim",
            title="Provider test",
            body="Generate a minimal HTML response for connection testing.",
        )
        html = self.controller.html_provider.render(state, (node,))
        return {"status": "ok", "html_length": len(html), **self._html_provider_summary()}


def create_app(
    data_root: Path,
    environ: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
) -> ApiApplication:
    config = ProviderConfig.from_environ(os.environ if environ is None else environ)
    if config.require_deepseek and not config.deepseek_enabled:
        raise ValueError(
            "DEEPSEEK_API_KEY is required when REQUIRE_DEEPSEEK is enabled"
        )
    store = EventStore(Path(data_root))
    if config.deepseek_enabled:
        provider = DeepSeekProvider(config, transport)
        provider_info = {"provider": "deepseek", "model": config.model}
    else:
        provider = DeterministicProvider()
        provider_info = {"provider": "deterministic-local"}
    html_provider = AestheticHtmlProvider()
    provider_info["html_provider"] = "aesthetic-markdown"
    provider_info["html_model"] = "swiss"
    return ApiApplication(
        Controller(store, provider, html_provider),
        provider_info,
        config,
        transport,
    )


class WorkspaceRequestHandler(BaseHTTPRequestHandler):
    application: ApiApplication
    web_root: Path

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            self._serve_api(method, path)
        elif method == "GET":
            self._serve_static(path)
        else:
            self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    def _serve_api(self, method: str, path: str) -> None:
        try:
            body = self._read_json() if method == "POST" else {}
            payload = self.application.handle(method, path, body)
            self._send_json(HTTPStatus.OK, payload)
        except KeyError as error:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
        except (ValueError, TypeError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception as error:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"服务器处理失败：{error}"},
            )

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in ("", "/") else request_path.lstrip("/")
        candidate = (self.web_root / relative).resolve()
        if self.web_root.resolve() not in candidate.parents and candidate != self.web_root.resolve():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = candidate.read_bytes()
        content_type, _ = mimetypes.guess_type(candidate.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        return


def run_server(host: str, port: int, data_root: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    handler = type(
        "BoundWorkspaceRequestHandler",
        (WorkspaceRequestHandler,),
        {
            "application": create_app(data_root),
            "web_root": root / "web",
        },
    )
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Agent workspace running at http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agent presentation workspace")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=4173, type=int)
    parser.add_argument("--data-root", default="data")
    args = parser.parse_args()
    run_server(args.host, args.port, Path(args.data_root))


if __name__ == "__main__":
    main()
