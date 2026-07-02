from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ProviderConfig:
    api_key: str
    model: str
    base_url: str
    timeout_seconds: float
    require_deepseek: bool = False
    ark_api_key: str = ""
    ark_model: str = "doubao-seed-1-6"
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_timeout_seconds: float = 60.0
    require_ark_html: bool = False

    @property
    def deepseek_enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def ark_html_enabled(self) -> bool:
        return bool(self.ark_api_key)

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> "ProviderConfig":
        raw_timeout = environ.get("DEEPSEEK_TIMEOUT_SECONDS", "60").strip()
        try:
            timeout = float(raw_timeout)
        except ValueError as error:
            raise ValueError(
                "DEEPSEEK_TIMEOUT_SECONDS must be a positive number"
            ) from error
        if timeout <= 0:
            raise ValueError("DEEPSEEK_TIMEOUT_SECONDS must be a positive number")

        raw_ark_timeout = environ.get("ARK_TIMEOUT_SECONDS", "60").strip()
        try:
            ark_timeout = float(raw_ark_timeout)
        except ValueError as error:
            raise ValueError(
                "ARK_TIMEOUT_SECONDS must be a positive number"
            ) from error
        if ark_timeout <= 0:
            raise ValueError("ARK_TIMEOUT_SECONDS must be a positive number")

        return cls(
            api_key=environ.get("DEEPSEEK_API_KEY", "").strip(),
            model=(
                environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()
                or "deepseek-v4-flash"
            ),
            base_url=(
                environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
                or "https://api.deepseek.com"
            ).rstrip("/"),
            timeout_seconds=timeout,
            require_deepseek=(
                environ.get("REQUIRE_DEEPSEEK", "").strip().lower()
                in {"1", "true", "yes", "on"}
            ),
            ark_api_key=environ.get("ARK_API_KEY", "").strip(),
            ark_model=(
                environ.get("ARK_MODEL", "doubao-seed-1-6").strip()
                or "doubao-seed-1-6"
            ),
            ark_base_url=(
                environ.get(
                    "ARK_BASE_URL",
                    "https://ark.cn-beijing.volces.com/api/v3",
                ).strip()
                or "https://ark.cn-beijing.volces.com/api/v3"
            ).rstrip("/"),
            ark_timeout_seconds=ark_timeout,
            require_ark_html=(
                environ.get("REQUIRE_ARK_HTML", "").strip().lower()
                in {"1", "true", "yes", "on"}
            ),
        )
