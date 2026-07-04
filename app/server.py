from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import os
import re
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from .agents import DeterministicProvider
from .aesthetic_html import AestheticHtmlProvider
from .deepseek import DeepSeekProvider, HttpTransport
from .domain import ContentNode, ProjectState
from .html_provider import LocalHtmlProvider
from .orchestrator import Controller
from .provider_config import ProviderConfig
from .store import ConflictError, EventStore

logger = logging.getLogger('presentools')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(handler)


RouteHandler = Callable[[str, str, dict[str, Any]], dict[str, Any]]
RoutePredicate = Callable[[str, str], bool]  # (method, path) -> bool


class ApiApplication:
    def __init__(
        self,
        controller: Controller,
        provider_info: dict[str, str] | None = None,
        config: ProviderConfig | None = None,
        transport: HttpTransport | None = None,
    ):
        self.controller = controller
        self.provider_info = provider_info or {'provider': 'deterministic-local'}
        self.config = config or ProviderConfig.from_environ({})
        self.transport = transport
        self._routes: list[tuple[RoutePredicate, RouteHandler]] = []
        self._build_routes()

    def _build_routes(self) -> None:
        self._routes = [
            (lambda m, p: m == 'GET' and p == '/api/health', self._get_health),
            (lambda m, p: m == 'GET' and p == '/api/html-provider', self._html_provider_summary),
            (lambda m, p: m == 'POST' and p == '/api/html-provider', self._configure_html_provider),
            (lambda m, p: m == 'POST' and p == '/api/html-provider/test', self._test_html_provider),
            (lambda m, p: m == 'POST' and bool(re.fullmatch(r'/api/projects/([^/]+)/analyze', p)), self._analyze_topic),
            (lambda m, p: m == 'POST' and bool(re.fullmatch(r'/api/projects/([^/]+)/script', p)), self._generate_script),
            (lambda m, p: m == 'POST' and bool(re.fullmatch(r'/api/projects/([^/]+)/comments', p)), self._submit_comment),
            (lambda m, p: m == 'POST' and bool(re.fullmatch(r'/api/projects/([^/]+)/nodes/([^/]+)/revision', p)), self._revise_node),
            (lambda m, p: m == 'POST' and bool(re.fullmatch(r'/api/projects/([^/]+)/nodes/([^/]+)/delete', p)), self._delete_node),
            (lambda m, p: m == 'POST' and bool(re.fullmatch(r'/api/projects/([^/]+)/proposals/([^/]+)/accept', p)), self._accept_proposal),
            (lambda m, p: m == 'POST' and bool(re.fullmatch(r'/api/projects/([^/]+)/proposals/([^/]+)/reject', p)), self._reject_proposal),
            (lambda m, p: m == 'POST' and bool(re.fullmatch(r'/api/projects/([^/]+)/html/preview', p)), self._preview_html),
            (lambda m, p: m == 'POST' and bool(re.fullmatch(r'/api/projects/([^/]+)/html/([^/]+)/lock', p)), self._lock_html_preview),
            (lambda m, p: m == 'POST' and bool(re.fullmatch(r'/api/projects/([^/]+)/artifacts/lock', p)), self._deprecated_lock_artifact),
            (lambda m, p: m == 'GET' and bool(re.fullmatch(r'/api/projects/([^/]+)/memory', p)), self._get_memory),
            (lambda m, p: m in ('GET', 'DELETE') and bool(re.fullmatch(r'/api/projects/([^/]+)', p)), self._get_or_delete_project),
            (lambda m, p: m == 'POST' and p == '/api/projects', self._create_project),
        ]

    def handle(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = body or {}
        try:
            for matches, handler_fn in self._routes:
                if matches(method, path):
                    return handler_fn(method, path, body)
            raise KeyError(f'Route not found: {method} {path}')
        except ConflictError as error:
            raise ValueError(f'\u5199\u5165\u51b2\u7a81\uff1a{error}') from error

    @staticmethod
    def _extract_ids(path: str, pattern: str) -> tuple[str, ...]:
        match = re.fullmatch(pattern, path)
        return match.groups() if match else ()

    # ===== Health =====

    def _get_health(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if method != 'GET':
            raise KeyError(f'Method not allowed: {method}')
        return {'status': 'ok', **self.provider_info}

    # ===== Project CRUD =====

    def _create_project(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if method != 'POST':
            raise KeyError(f'Method not allowed: {method}')
        title = str(body.get('title', '')).strip()
        audience = str(body.get('audience', '')).strip()
        if not title:
            raise ValueError('\u9879\u76ee\u4e3b\u9898\u4e0d\u80fd\u4e3a\u7a7a')
        if not audience:
            raise ValueError('\u76ee\u6807\u53d7\u4f17\u4e0d\u80fd\u4e3a\u7a7a')
        logger.info(f'Creating project: {title}')
        return self.controller.create_project(title, audience).to_dict()

    def _get_or_delete_project(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        ids = self._extract_ids(path, r'/api/projects/([^/]+)')
        project_id = ids[0]
        if method == 'GET':
            return self.controller.store.project(project_id).to_dict()
        if method == 'DELETE':
            return {'message': '\u8f6f\u5220\u9664\u529f\u80fd\u8bf7\u76f4\u63a5\u5220\u9664 data/ \u4e0b\u7684\u5bf9\u5e94 JSONL \u6587\u4ef6\u3002'}
        raise KeyError(f'Method not allowed: {method}')

    # ===== Analysis =====

    def _analyze_topic(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if method != 'POST':
            raise KeyError(f'Method not allowed: {method}')
        ids = self._extract_ids(path, r'/api/projects/([^/]+)/analyze')
        logger.info(f'Starting analysis for {ids[0]}')
        return self.controller.analyze_topic(ids[0]).to_dict()

    # ===== Script =====

    def _generate_script(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if method != 'POST':
            raise KeyError(f'Method not allowed: {method}')
        ids = self._extract_ids(path, r'/api/projects/([^/]+)/script')
        logger.info(f'Generating script for {ids[0]}')
        proposal = self.controller.generate_script(ids[0])
        return {
            **proposal.__dict__,
            'changes': list(proposal.changes),
            'affected_ids': list(proposal.affected_ids),
        }

    # ===== Comments =====

    def _submit_comment(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if method != 'POST':
            raise KeyError(f'Method not allowed: {method}')
        ids = self._extract_ids(path, r'/api/projects/([^/]+)/comments')
        proposal = self.controller.submit_comment(ids[0], str(body.get('text', '')), body.get('target_id'))
        return {
            **proposal.__dict__,
            'changes': list(proposal.changes),
            'affected_ids': list(proposal.affected_ids),
        }

    # ===== Revision =====

    def _revise_node(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if method != 'POST':
            raise KeyError(f'Method not allowed: {method}')
        ids = self._extract_ids(path, r'/api/projects/([^/]+)/nodes/([^/]+)/revision')
        proposal = self.controller.revise_node(ids[0], ids[1], str(body.get('title', '')), str(body.get('body', '')))
        return {
            **proposal.__dict__,
            'changes': list(proposal.changes),
            'affected_ids': list(proposal.affected_ids),
        }

    # ===== Delete node =====

    def _delete_node(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if method != 'POST':
            raise KeyError(f'Method not allowed: {method}')
        ids = self._extract_ids(path, r'/api/projects/([^/]+)/nodes/([^/]+)/delete')
        proposal = self.controller.delete_node(ids[0], ids[1], str(body.get('reason', '')))
        return {
            **proposal.__dict__,
            'changes': list(proposal.changes),
            'affected_ids': list(proposal.affected_ids),
        }

    # ===== Proposals =====

    def _accept_proposal(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if method != 'POST':
            raise KeyError(f'Method not allowed: {method}')
        ids = self._extract_ids(path, r'/api/projects/([^/]+)/proposals/([^/]+)/accept')
        logger.info(f'Accepting proposal {ids[1]} in {ids[0]}')
        proposal = self.controller.accept_proposal(ids[0], ids[1])
        return {
            **proposal.__dict__,
            'changes': list(proposal.changes),
            'affected_ids': list(proposal.affected_ids),
        }

    def _reject_proposal(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if method != 'POST':
            raise KeyError(f'Method not allowed: {method}')
        ids = self._extract_ids(path, r'/api/projects/([^/]+)/proposals/([^/]+)/reject')
        logger.info(f'Rejecting proposal {ids[1]} in {ids[0]}')
        proposal = self.controller.reject_proposal(ids[0], ids[1])
        return {
            **proposal.__dict__,
            'changes': list(proposal.changes),
            'affected_ids': list(proposal.affected_ids),
        }

    # ===== HTML =====

    def _preview_html(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if method != 'POST':
            raise KeyError(f'Method not allowed: {method}')
        ids = self._extract_ids(path, r'/api/projects/([^/]+)/html/preview')
        name = str(body.get('name', 'HTML \u9884\u89c8')).strip() or 'HTML \u9884\u89c8'
        artifact = self.controller.preview_html(ids[0], name)
        return {**asdict(artifact), 'node_ids': list(artifact.node_ids)}

    def _lock_html_preview(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if method != 'POST':
            raise KeyError(f'Method not allowed: {method}')
        ids = self._extract_ids(path, r'/api/projects/([^/]+)/html/([^/]+)/lock')
        artifact = self.controller.lock_html_preview(ids[0], ids[1])
        return {**asdict(artifact), 'node_ids': list(artifact.node_ids)}

    def _deprecated_lock_artifact(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if method != 'POST':
            raise KeyError(f'Method not allowed: {method}')
        ids = self._extract_ids(path, r'/api/projects/([^/]+)/artifacts/lock')
        name = str(body.get('name', '\u6b63\u5f0f\u7248')).strip() or '\u6b63\u5f0f\u7248'
        logger.warning(f'Deprecated /artifacts/lock called for {ids[0]}. Please use /html/preview followed by /html/{{id}}/lock instead.')
        artifact = self.controller.lock_artifact(ids[0], name)
        return {**asdict(artifact), 'node_ids': list(artifact.node_ids)}

    # ===== Memory =====

    def _get_memory(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if method != 'GET':
            raise KeyError(f'Method not allowed: {method}')
        ids = self._extract_ids(path, r'/api/projects/([^/]+)/memory')
        return {'markdown': self.controller.memory_markdown(ids[0])}

    # ===== HTML Provider config =====

    def _html_provider_summary(self, method: str = '', path: str = '', body: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.provider_info.get('html_provider') == 'aesthetic-markdown':
            return {'provider': 'aesthetic-markdown', 'model': self.provider_info.get('html_model', 'swiss'), 'base_url': '', 'key_configured': False, 'require_remote': False}
        return {'provider': 'local-template', 'model': '', 'base_url': '', 'key_configured': False, 'require_remote': False}

    def _configure_html_provider(self, method: str = '', path: str = '', body: dict[str, Any] | None = None) -> dict[str, Any]:
        body = body or {}
        provider = str(body.get('provider', 'local-template')).strip()
        if provider in {'aesthetic', 'aesthetic-markdown'}:
            paradigm = str(body.get('model', 'swiss')).strip() or 'swiss'
            self.controller.html_provider = AestheticHtmlProvider(paradigm)
            self.provider_info['html_provider'] = 'aesthetic-markdown'
            self.provider_info['html_model'] = paradigm
            logger.info(f'Switched HTML provider to aesthetic-markdown ({paradigm})')
            return self._html_provider_summary()
        if provider in {'local', 'local-template'}:
            self.controller.html_provider = LocalHtmlProvider()
            self.provider_info['html_provider'] = 'local-template'
            self.provider_info.pop('html_model', None)
            logger.info('Switched HTML provider to local-template')
            return self._html_provider_summary()
        raise ValueError(f'\u4e0d\u652f\u6301\u7684 HTML \u751f\u6210\u5f15\u64ce\uff1a{provider}')

    def _test_html_provider(self, method: str = '', path: str = '', body: dict[str, Any] | None = None) -> dict[str, Any]:
        state = ProjectState(id='provider-test', title='HTML \u751f\u6210\u5f15\u64ce\u6d4b\u8bd5', audience='\u5185\u90e8\u6d4b\u8bd5')
        node = ContentNode(id='node-provider-test', kind='claim', title='\u5f15\u64ce\u8fde\u63a5\u6d4b\u8bd5', body='\u8bf7\u4e3a\u6d4b\u8bd5\u76ee\u7684\u751f\u6210\u4e00\u4e2a\u6700\u7b80 HTML \u54cd\u5e94\uff0c\u9a8c\u8bc1\u751f\u6210\u5f15\u64ce\u5df2\u6b63\u786e\u914d\u7f6e\u3002')
        html = self.controller.html_provider.render(state, (node,))
        return {'status': 'ok', 'html_length': len(html), **self._html_provider_summary()}
def create_app(
    data_root: Path,
    environ: Mapping[str, str] | None = None,
    transport: HttpTransport | None = None,
) -> ApiApplication:
    config = ProviderConfig.from_environ(os.environ if environ is None else environ)
    if config.require_deepseek and not config.deepseek_enabled:
        raise ValueError("当 REQUIRE_DEEPSEEK 启用时，必须设置 DEEPSEEK_API_KEY")
    store = EventStore(Path(data_root))
    if config.deepseek_enabled:
        provider = DeepSeekProvider(config, transport)
        provider_info = {"provider": "deepseek", "model": config.model}
        logger.info(f"Using DeepSeek provider ({config.model})")
    else:
        provider = DeterministicProvider()
        provider_info = {"provider": "deterministic-local"}
        logger.info("Using deterministic local provider (no API key configured)")
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

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

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
            body = self._read_json() if method in ("POST", "DELETE") else {}
            payload = self.application.handle(method, path, body)
            self._send_json(HTTPStatus.OK, payload)
        except KeyError as error:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(error)})
        except (ValueError, TypeError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception as error:
            logger.exception("Unhandled server error")
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
        logger.debug("%s - %s", self.client_address[0], format % args)


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
    logger.info(f"叙构工作台已启动 → http://{host}:{port}")
    print(f"叙构工作台已启动 → http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="启动叙构 Agent 原生演示工作台")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认：127.0.0.1）")
    parser.add_argument("--port", default=4173, type=int, help="监听端口（默认：4173）")
    parser.add_argument("--data-root", default="data", help="事件存储目录（默认：data）")
    args = parser.parse_args()
    run_server(args.host, args.port, Path(args.data_root))


if __name__ == "__main__":
    main()
