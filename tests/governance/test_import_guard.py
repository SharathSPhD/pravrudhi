import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "import_guard.py"


def _run(root: Path) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(GUARD), "--root", str(root)], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def test_repo_is_clean() -> None:
    rc, out = _run(ROOT)
    assert rc == 0, out


def test_planted_kernel_import_of_engine_is_caught(tmp_path: Path) -> None:
    k = tmp_path / "pravrudhi_kernel" / "src" / "pravrudhi_kernel"
    k.mkdir(parents=True)
    (k / "bad.py").write_text("from pravrudhi import something\n")
    rc, out = _run(tmp_path)
    assert rc == 1 and "bad.py:1" in out


def test_planted_torch_in_domain_is_caught(tmp_path: Path) -> None:
    d = tmp_path / "src" / "pravrudhi" / "domain"
    d.mkdir(parents=True)
    (d / "bad.py").write_text("import torch\n")
    rc, out = _run(tmp_path)
    assert rc == 1 and "bad.py:1" in out
