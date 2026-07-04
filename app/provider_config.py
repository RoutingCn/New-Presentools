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

    @property
    def deepseek_enabled(self) -> bool:
        return bool(self.api_key)

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
        )
