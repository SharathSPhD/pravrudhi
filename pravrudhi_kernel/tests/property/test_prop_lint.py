"""Every public function in pravrudhi_kernel.stats must have a test_prop_<name>* test."""

import importlib
import inspect
import pkgutil
import re
from pathlib import Path

import pravrudhi_kernel.stats as stats_pkg


def test_every_public_stats_function_has_a_property_test() -> None:
    names: set[str] = set()
    for m in pkgutil.iter_modules(stats_pkg.__path__):
        mod = importlib.import_module(f"pravrudhi_kernel.stats.{m.name}")
        for n, obj in inspect.getmembers(mod, inspect.isfunction):
            if obj.__module__ == mod.__name__ and not n.startswith("_"):
                names.add(n)
    src = "\n".join(p.read_text() for p in Path(__file__).parent.glob("test_prop_*.py"))
    tested = set(re.findall(r"def test_prop_([a-z0-9_]+)", src))
    missing = sorted(n for n in names if not any(t.startswith(n) for t in tested))
    assert not missing, f"public stats functions without test_prop_*: {missing}"
