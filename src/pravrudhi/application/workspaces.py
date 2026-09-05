"""Per-user workspace layout for Pravrudhi's multi-user surface.

`docs/superpowers/specs/2026-09-05-pravrudhi-multitenant-design.md`'s Amendment ("one ledger per
workspace, no kernel change") decided that isolation between users is the filesystem's job, not a
`user_id` column threaded through the kernel's hash-chained ledger: a shared ledger with an owner column
would look cryptographically isolated without being so, since the hash chain proves a sequence of events
was not altered but proves nothing about who wrote the `user_id` field inside one. A workspace is instead
just a directory, `${PRAVRUDHI_WORKSPACES}/<user_id>/<slug>/`, created on first use by the same
`init_project` a local user already runs — so a hosted account's first workspace and a laptop's first
workspace are the same code path and the same layout.

Shape (a), the local single-user install, never calls into this module: it runs from the checkout it was
started in and never sees this tree. This module exists only for the hosted shapes (b) and (c), and it
holds no Supabase table code — only the filesystem layout that a user id and a workspace slug resolve to.
"""

from __future__ import annotations

import os
from pathlib import Path

from pravrudhi.application.init import init_project
from pravrudhi.application.objectives import ID_RE

DEFAULT_WORKSPACES = Path.home() / ".pravrudhi" / "workspaces"


class WorkspaceError(ValueError):
    """A workspace path that would escape its user's directory or the workspaces root is not a workspace."""


def workspaces_root() -> Path:
    raw = os.environ.get("PRAVRUDHI_WORKSPACES", "")
    return Path(raw).expanduser() if raw else DEFAULT_WORKSPACES


def _safe_segment(value: str, *, label: str) -> str:
    """A path segment that cannot walk out of its parent directory."""
    v = (value or "").strip()
    if not v or "/" in v or "\\" in v or ".." in v:
        raise WorkspaceError(f"{label} {value!r} contains a path separator or '..'")
    return v


def _safe_slug(slug: str) -> str:
    if not ID_RE.match(slug or ""):
        raise WorkspaceError(f"workspace slug {slug!r} must be lowercase letters, digits and hyphens (2-63 chars)")
    return slug


def workspace_dir(user_id: str, slug: str) -> Path:
    """The directory for one user's one workspace. Raises `WorkspaceError` rather than resolve to
    anything outside `workspaces_root()`."""
    uid = _safe_segment(user_id, label="user id")
    safe_slug = _safe_slug(slug)
    root = workspaces_root().resolve()
    path = (root / uid / safe_slug).resolve()
    if path != root and root not in path.parents:
        raise WorkspaceError(f"workspace path for user {user_id!r} slug {slug!r} escapes {root}")
    return path


def ensure_workspace(user_id: str, slug: str) -> Path:
    """The workspace directory, created and initialised on first use.

    Idempotent because `init_project` is: it never overwrites an existing config or ledger, so calling
    this again for the same user and slug only confirms the workspace still exists.
    """
    path = workspace_dir(user_id, slug)
    path.mkdir(parents=True, exist_ok=True)
    init_project(path)
    return path


def list_workspaces(user_id: str) -> list[str]:
    """Every workspace slug this user has created, sorted."""
    uid = _safe_segment(user_id, label="user id")
    user_dir = workspaces_root() / uid
    if not user_dir.exists():
        return []
    return sorted(p.name for p in user_dir.iterdir() if p.is_dir())
