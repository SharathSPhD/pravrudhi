"""Minimal YAML config loader for this proposal's flat config file.

Avoids a hard dependency on PyYAML so the recipe scripts run with a stock
Python + stdlib install. Only supports the subset of YAML used by
configs/retrieval.yaml: flat `key: scalar` pairs and one level of
`key:` followed by `- item` list entries. Not a general YAML parser.
"""

from __future__ import annotations


def _coerce_scalar(raw: str) -> object:
    raw = raw.strip()
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw.strip("'\"")


def load_simple_yaml(path: str) -> dict:
    config: dict = {}
    current_list_key: str | None = None

    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.split("#", 1)[0].rstrip()
            if not line.strip():
                continue

            if line.lstrip().startswith("- "):
                if current_list_key is None:
                    raise ValueError(f"list item with no preceding key: {raw_line!r}")
                config.setdefault(current_list_key, []).append(
                    _coerce_scalar(line.lstrip()[2:])
                )
                continue

            if ":" not in line:
                raise ValueError(f"cannot parse config line: {raw_line!r}")

            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            if value == "":
                current_list_key = key
                config[key] = []
            else:
                current_list_key = None
                config[key] = _coerce_scalar(value)

    return config
