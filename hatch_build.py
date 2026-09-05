"""Ship the built web interface inside the wheel, when it has been built.

`app/frontend/out` is a build product outside `src/`, gitignored, and absent from a clean checkout. A static
`force-include` entry pointing at it would couple every wheel build to a prior `npm run build`. This hook adds the
mapping only when the directory is present, so `uv build --wheel` works on a clean tree and produces a complete
wheel on a tree where the interface has been built.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

EXPORT = Path("app") / "frontend" / "out"
TARGET = "pravrudhi/assets/frontend"


class FrontendHook(BuildHookInterface):  # type: ignore[type-arg]
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        export = Path(self.root) / EXPORT
        if (export / "index.html").exists():
            build_data.setdefault("force_include", {})[str(export)] = TARGET
