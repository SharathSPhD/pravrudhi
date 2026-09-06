"""The second internal code pool: an APPS slice sealed as `solve(stdin) -> str` problems (ADR-0029).

MBPP+ was the harness track's only internal pool and 378 problems at exposure cap 8 is spent, so a night now
dies at `draw_rotation` before it evaluates anything. HumanEval+ cannot take over: it is the external check the
track reports against. These tests pin the contract that lets a second pool arrive without changing the agent
job or the harness grammar -- one visible `assert` in the question, every other test hidden in the answer, a
scorer chosen by the pool's own bench name, and a candidate executed out of process so a hang costs one test
rather than the whole rotation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "docker" / "jobs"))

from apps_check import run_solve  # noqa: E402
from checks import visible_tests  # noqa: E402

from pravrudhi.application.harness_track import SCORERS, _scorer  # noqa: E402
from pravrudhi.application.pool_admin import seal_apps  # noqa: E402
from pravrudhi_kernel.metrics.pool import load_manifest, read_item  # noqa: E402

SUM_SOLVE = "def solve(stdin):\n    return str(sum(int(x) for x in stdin.split())) + '\\n'\n"


def _problem(pid: int, difficulty: str, io: dict[str, Any]) -> dict[str, Any]:
    return {
        "problem_id": pid,
        "question": f"Problem {pid}: read the numbers and print their sum.",
        "input_output": json.dumps(io),
        "difficulty": difficulty,
        "solutions": json.dumps([SUM_SOLVE]),
    }


def _stdin_io(n: int) -> dict[str, Any]:
    return {"inputs": [f"{i} {i}\n" for i in range(n)], "outputs": [f"{2 * i}\n" for i in range(n)]}


def _fixture(tmp_path: Path) -> Path:
    """Six APPS rows in the codeparrot/apps column shape: four sealable, one out-of-scope difficulty, one
    call-based problem the `solve(stdin)` contract cannot express."""
    rows = [
        _problem(10, "introductory", _stdin_io(4)),
        _problem(11, "interview", _stdin_io(3)),
        _problem(12, "introductory", _stdin_io(5)),
        _problem(13, "interview", _stdin_io(2)),
        _problem(14, "competition", _stdin_io(4)),
        _problem(15, "introductory", {"inputs": [[1, 2], [3, 4]], "outputs": [3, 7], "fn_name": "add"}),
    ]
    p = tmp_path / "apps_test.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def test_seal_apps_keeps_one_visible_assert_and_hides_the_rest(tmp_path: Path) -> None:
    root = tmp_path / "root"
    manifest = seal_apps(root, _fixture(tmp_path), count=3, seed=7)
    assert manifest["bench"] == "apps"
    assert manifest["n_items"] == 3
    assert manifest["source"]["draw"] == {
        "seed": 7,
        "count": 3,
        "difficulties": ["introductory", "interview"],
        "min_tests": 2,
        "max_hidden_tests": 12,
        "n_eligible": 4,
    }
    pool = root / ".pravrudhi" / "kernel" / "pools" / "apps"
    for item_id in load_manifest(pool)["item_hashes"]:
        item = read_item(pool, item_id)
        answer = json.loads(item["answer"])
        assert answer["fn_name"] == "solve"
        assert answer["task_id"] in {"10", "11", "12", "13"}
        # exactly one visible check, and it is the first pair rendered as an assert the executor already reads
        checks = visible_tests(item["question"])
        assert checks == ["assert solve('0 0\\n') == '0\\n'"]
        assert item["question"].count("assert solve(") == 1
        # the hidden pairs are the remaining ones and appear nowhere in the question
        assert answer["inputs"] == [f"{i} {i}\n" for i in range(1, len(answer["inputs"]) + 1)]
        assert answer["outputs"] == [f"{2 * i}\n" for i in range(1, len(answer["outputs"]) + 1)]
        assert "1 1" not in item["question"]


def test_seal_apps_draw_is_deterministic_in_the_seed(tmp_path: Path) -> None:
    src = _fixture(tmp_path)

    def drawn(root: Path, seed: int) -> list[str]:
        seal_apps(root, src, count=3, seed=seed)
        pool = root / ".pravrudhi" / "kernel" / "pools" / "apps"
        ids = sorted(load_manifest(pool)["item_hashes"])
        return [json.loads(read_item(pool, i)["answer"])["task_id"] for i in ids]

    assert drawn(tmp_path / "a", 7) == drawn(tmp_path / "b", 7)


def test_seal_apps_refuses_a_count_the_slice_cannot_fill(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="eligible APPS problems"):
        seal_apps(tmp_path / "root", _fixture(tmp_path), count=5, seed=7)


def test_run_solve_passes_a_correct_candidate() -> None:
    res = run_solve(SUM_SOLVE, ["1 2\n", "3 4\n"], ["3\n", "7 \n"], timeout_s=10.0)
    assert res == {"passed": 2, "total": 2, "failures": []}


def test_run_solve_fails_a_wrong_candidate() -> None:
    res = run_solve("def solve(stdin):\n    return '0\\n'\n", ["1 2\n"], ["3\n"], timeout_s=10.0)
    assert res["passed"] == 0
    assert res["total"] == 1
    assert "expected '3', got '0'" in res["failures"][0]


def test_run_solve_reports_a_hang_as_one_failed_test() -> None:
    res = run_solve("def solve(stdin):\n    while True:\n        pass\n", ["1\n"], ["1\n"], timeout_s=1.0)
    assert res["passed"] == 0
    assert res["failures"] == ["test 0: timeout after 1s"]


def test_run_solve_reports_a_candidate_that_never_defines_solve() -> None:
    res = run_solve("x = 1\n", ["1\n"], ["1\n"], timeout_s=10.0)
    assert res["passed"] == 0
    assert "solve is not defined" in res["failures"][0]


def test_scorer_is_selected_by_the_pools_bench_name(tmp_path: Path) -> None:
    root = tmp_path / "root"
    seal_apps(root, _fixture(tmp_path), count=3, seed=7)
    scorer, needs_pool = _scorer(root / ".pravrudhi" / "kernel" / "pools" / "apps")
    assert scorer.name == "score_apps.py"
    assert scorer.exists()
    assert needs_pool is True
    assert SCORERS["mbppplus"] == ("score_code.py", False)


def test_the_jsonl_export_keys_its_id_as_id_not_problem_id(tmp_path: Path) -> None:
    """The parquet conversion names it `problem_id`; the JSONL the dataset ships names it `id`, and sealing read
    only the first, so the real download failed with a KeyError."""
    from pravrudhi.application.pool_admin import _apps_task_id

    assert _apps_task_id({"problem_id": 7}) == "7"
    assert _apps_task_id({"id": 9}) == "9"
    assert _apps_task_id({"problem_id": 1, "id": 2}) == "1", "the parquet name wins when both are present"
    assert _apps_task_id({"question": "no id at all"}) is None
