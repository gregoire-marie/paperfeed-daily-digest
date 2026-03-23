from __future__ import annotations

import os
from pathlib import Path

from paperfeed.models import (
    DigestPreferences,
    LlamaCppConfig,
    PaperFeedConfig,
    PaperSeed,
    SummarizerConfig,
)


def load_config(path: str | Path) -> PaperFeedConfig:
    config_path = Path(path)
    raw = _parse_seeds_yaml(config_path.read_text(encoding="utf-8"))

    positive_seeds = [_seed_from_dict(item) for item in raw.get("positive_seeds", [])]
    negative_seeds = [_seed_from_dict(item) for item in raw.get("negative_seeds", [])]
    preferences = DigestPreferences(**raw.get("preferences", {}))
    return PaperFeedConfig(
        positive_seeds=positive_seeds,
        negative_seeds=negative_seeds,
        preferences=preferences,
    )


def load_summarizer_config(
    *,
    backend: str | None = None,
    llama_base_url: str | None = None,
    llama_model: str | None = None,
    llama_api_key: str | None = None,
    llama_temperature: float | None = None,
    llama_timeout_seconds: float | None = None,
) -> SummarizerConfig:
    resolved_backend = backend or os.getenv("PAPERFEED_SUMMARIZER_BACKEND", "deterministic")
    resolved_base_url = llama_base_url or os.getenv(
        "LLAMA_CPP_BASE_URL",
        "http://127.0.0.1:8080/v1",
    )
    resolved_model = llama_model or os.getenv("LLAMA_CPP_MODEL", "local-model")
    resolved_api_key = (
        llama_api_key
        if llama_api_key is not None
        else _optional_string(os.getenv("LLAMA_CPP_API_KEY"))
    )
    resolved_temperature = (
        llama_temperature
        if llama_temperature is not None
        else _float_from_env("LLAMA_CPP_TEMPERATURE", default=0.1)
    )
    resolved_timeout = (
        llama_timeout_seconds
        if llama_timeout_seconds is not None
        else _float_from_env("LLAMA_CPP_TIMEOUT_SECONDS", default=60.0)
    )

    return SummarizerConfig(
        backend=resolved_backend,
        llama_cpp=LlamaCppConfig(
            base_url=resolved_base_url,
            model=resolved_model,
            api_key=resolved_api_key,
            temperature=resolved_temperature,
            timeout_seconds=resolved_timeout,
        ),
    )


def _seed_from_dict(data: dict[str, object]) -> PaperSeed:
    if "doi" in data:
        return PaperSeed(doi=_expect_string(data["doi"], "seed.doi"))
    if "paper_id" in data:
        return PaperSeed(paper_id=_expect_string(data["paper_id"], "seed.paper_id"))
    raise ValueError("Seed entries must contain either doi or paper_id.")


def _parse_seeds_yaml(text: str) -> dict[str, object]:
    result: dict[str, object] = {}
    current_section: str | None = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw_line).rstrip()
        if not line.strip():
            continue
        if "\t" in raw_line:
            raise ValueError(f"Tabs are not supported in seeds.yaml (line {line_number}).")

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            if stripped.endswith(":"):
                current_section = stripped[:-1]
                if current_section in {"positive_seeds", "negative_seeds"}:
                    result[current_section] = []
                elif current_section == "preferences":
                    result[current_section] = {}
                else:
                    raise ValueError(f"Unsupported top-level key '{current_section}' at line {line_number}.")
                continue

            key, value = _split_key_value(stripped, line_number)
            if key not in {"positive_seeds", "negative_seeds"}:
                raise ValueError(f"Unsupported inline top-level key '{key}' at line {line_number}.")
            if value != "[]":
                raise ValueError(f"Only empty inline lists are supported for '{key}' at line {line_number}.")
            result[key] = []
            current_section = key
            continue

        if current_section is None:
            raise ValueError(f"Found nested content before a section header at line {line_number}.")

        if current_section in {"positive_seeds", "negative_seeds"}:
            if indent != 2 or not stripped.startswith("- "):
                raise ValueError(f"Expected a list item under '{current_section}' at line {line_number}.")
            item_key, item_value = _split_key_value(stripped[2:], line_number)
            if item_key not in {"doi", "paper_id"}:
                raise ValueError(f"Unsupported seed key '{item_key}' at line {line_number}.")
            result.setdefault(current_section, []).append({item_key: _parse_scalar(item_value)})
            continue

        if current_section == "preferences":
            if indent != 2:
                raise ValueError(f"Expected a preference entry at line {line_number}.")
            pref_key, pref_value = _split_key_value(stripped, line_number)
            result.setdefault("preferences", {})[pref_key] = _parse_scalar(pref_value)
            continue

        raise ValueError(f"Unsupported section '{current_section}' at line {line_number}.")

    return result


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False

    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return line[:index]
    return line


def _split_key_value(text: str, line_number: int) -> tuple[str, str]:
    if ":" not in text:
        raise ValueError(f"Expected key/value pair at line {line_number}.")
    key, value = text.split(":", 1)
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> object:
    if value in {"", "null", "~"}:
        return None
    if value == "[]":
        return []
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        return value[1:-1]
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.isdigit():
        return int(value)
    return value


def _expect_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string.")
    return value


def _optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _float_from_env(name: str, *, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid float.") from exc
