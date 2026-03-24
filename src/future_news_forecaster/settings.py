from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def default_env_path() -> Path:
    return DEFAULT_ENV_PATH


def load_environment(env_path: Path | None = None) -> None:
    path = env_path or DEFAULT_ENV_PATH
    if path.exists():
        load_dotenv(path, override=False)


def read_env_file(env_path: Path | None = None) -> dict[str, str]:
    path = env_path or DEFAULT_ENV_PATH
    data: dict[str, str] = {}
    if not path.exists():
        return data

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def current_env_value(key: str, env_path: Path | None = None) -> str | None:
    load_environment(env_path)
    if os.environ.get(key):
        return os.environ[key]
    return read_env_file(env_path).get(key)


def save_env_value(key: str, value: str, env_path: Path | None = None) -> Path:
    path = env_path or DEFAULT_ENV_PATH
    payload = read_env_file(path)
    payload[key] = value.strip()

    ordered_keys = sorted(payload.keys())
    lines = [f"{name}={payload[name]}" for name in ordered_keys if payload[name]]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    os.environ[key] = value.strip()
    return path


def current_openai_api_key(env_path: Path | None = None) -> str | None:
    return current_env_value("OPENAI_API_KEY", env_path=env_path)


def save_openai_api_key(api_key: str, env_path: Path | None = None) -> Path:
    return save_env_value("OPENAI_API_KEY", api_key, env_path=env_path)
