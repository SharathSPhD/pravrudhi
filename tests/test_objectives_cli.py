"""Tests for objective and recipes CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from pravrudhi.cli.app import app
from pravrudhi_kernel.ledger import LedgerWriter

runner = CliRunner()


def _invoke(*args, **kwargs) -> object:
    """Wrapper to invoke the CLI with consistent defaults."""
    result = runner.invoke(app, args, **kwargs)
    return result


def test_objective_new_from_packaged_example(tmp_path: Path) -> None:
    """objective new --from prabhasa-nyaya writes the file and reports where."""
    # When using --from, the copied example keeps its own ID (prabhasa-nyaya)
    result = _invoke("objective", "new", "ignored-id", "--from", "prabhasa-nyaya", "--root", str(tmp_path))
    assert result.exit_code == 0
    assert "wrote" in result.stdout
    assert ".pravrudhi/objectives" in result.stdout

    # Verify the file was created with the packaged example's ID
    obj_file = tmp_path / ".pravrudhi" / "objectives" / "prabhasa-nyaya.yaml"
    assert obj_file.exists()
    obj = yaml.safe_load(obj_file.read_text())
    assert obj["intent"]  # copied intent
    assert obj["track"]


def test_objective_new_with_all_options(tmp_path: Path) -> None:
    """objective new with intent, track and metric writes a valid objective."""
    result = _invoke(
        "objective",
        "new",
        "my-model",
        "--intent", "improve accuracy on GSM8K",
        "--track", "model",
        "--metric", "acc,none",
        "--root", str(tmp_path),
    )
    assert result.exit_code == 0
    assert "wrote" in result.stdout

    obj_file = tmp_path / ".pravrudhi" / "objectives" / "my-model.yaml"
    assert obj_file.exists()
    obj = yaml.safe_load(obj_file.read_text())
    assert obj["intent"] == "improve accuracy on GSM8K"
    assert obj["track"] == "model"
    assert obj["benchmarks"][0]["metric"] == "acc,none"


def test_objective_new_missing_metric_exits_nonzero(tmp_path: Path) -> None:
    """objective new missing metric exits non-zero and says what is missing."""
    result = runner.invoke(
        app,
        [
            "objective",
            "new",
            "incomplete",
            "--intent", "do something",
            "--track", "mytrack",
            "--root", str(tmp_path),
        ],
    )
    assert result.exit_code == 2
    # Error messages might be in stdout or stderr, so check the full output
    output = (result.stdout or "") + (result.stderr or "")
    assert "metric" in output.lower()
    # Should list available examples
    assert "--from" in output


def test_objective_new_missing_intent_exits_nonzero(tmp_path: Path) -> None:
    """objective new missing intent should exit non-zero."""
    result = runner.invoke(
        app,
        [
            "objective",
            "new",
            "incomplete",
            "--track", "mytrack",
            "--metric", "something",
            "--root", str(tmp_path),
        ],
    )
    assert result.exit_code == 2
    output = (result.stdout or "") + (result.stderr or "")
    assert "--intent" in output or "intent" in output.lower()


def test_objective_new_missing_track_exits_nonzero(tmp_path: Path) -> None:
    """objective new missing track should exit non-zero."""
    result = runner.invoke(
        app,
        [
            "objective",
            "new",
            "incomplete",
            "--intent", "something",
            "--metric", "something",
            "--root", str(tmp_path),
        ],
    )
    assert result.exit_code == 2


def test_objective_list_empty_workspace_helpful(tmp_path: Path) -> None:
    """objective list on empty workspace tells user how to make one rather than nothing."""
    result = _invoke("objective", "list", "--root", str(tmp_path))
    assert result.exit_code == 0
    # Should give a helpful suggestion
    assert "no objectives yet" in result.stdout
    assert "objective new" in result.stdout or "prabhasa-nyaya" in result.stdout


def test_objective_progress_unmeasured_no_ledger(tmp_path: Path) -> None:
    """objective progress on objective with no ledger rows says unmeasured and the reason, not 0.0000."""
    # Create an objective
    obj_dir = tmp_path / ".pravrudhi" / "objectives"
    obj_dir.mkdir(parents=True)
    obj = {
        "intent": "test objective",
        "track": "test",
        "benchmarks": [{"id": "bench", "tool": "lm-eval", "metric": "test-metric acc,none"}],
    }
    (obj_dir / "test-obj.yaml").write_text(yaml.dump(obj))

    # Create an empty ledger (ledger file exists but has no rows)
    ledger = tmp_path / "research" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    LedgerWriter.open(ledger, "0.1.0")  # a genesis-only ledger: it exists and holds no external result

    result = _invoke("objective", "progress", "test-obj", "--root", str(tmp_path))
    assert result.exit_code == 0
    assert "unmeasured" in result.stdout
    # Should NOT print 0.0000
    assert "0.0000" not in result.stdout
    # Should print the reason
    assert "no external result" in result.stdout


def test_objective_progress_baseline_only(tmp_path: Path) -> None:
    """objective progress with baseline but no candidate."""
    # Create an objective
    obj_dir = tmp_path / ".pravrudhi" / "objectives"
    obj_dir.mkdir(parents=True)
    obj = {
        "intent": "test objective",
        "track": "test-track",
        "benchmarks": [{"id": "bench", "tool": "lm-eval", "metric": "bench-name acc,none"}],
    }
    (obj_dir / "test-obj.yaml").write_text(yaml.dump(obj))

    # Build a ledger with just a baseline
    ledger = tmp_path / "research" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    w = LedgerWriter.open(ledger, "0.1.0")
    payload = {
        "kind": "external_eval",
        "severity": "info",
        "tier": "external",
        "track": "test-track",
        "condition": "base",
        "model": "Qwen/Qwen3-0.6B",
        "sha256": "0" * 64,
        "tool": "lm-eval",
        "n_samples": {"bench-name": 1000},
        "metrics": {"bench-name": {"acc,none": 0.42, "acc_stderr,none": 0.01}},
    }
    w.append("audit", "auditor", payload, epoch=0, night=1)

    result = _invoke("objective", "progress", "test-obj", "--root", str(tmp_path))
    assert result.exit_code == 0
    assert "baseline" in result.stdout
    assert "0.4200" in result.stdout
    # Baseline only state means current won't be shown
    output = result.stdout.lower()
    assert "baseline_only" in output or "nothing has been compared" in output


def test_objective_progress_with_baseline_and_candidate(tmp_path: Path) -> None:
    """objective progress with baseline and candidate prints both and the difference."""
    # Create an objective
    obj_dir = tmp_path / ".pravrudhi" / "objectives"
    obj_dir.mkdir(parents=True)
    obj = {
        "intent": "test objective",
        "track": "test-track",
        "benchmarks": [{"id": "bench", "tool": "lm-eval", "metric": "bench-name acc,none"}],
    }
    (obj_dir / "test-obj.yaml").write_text(yaml.dump(obj))

    # Build a ledger with baseline and candidate
    ledger = tmp_path / "research" / "ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    w = LedgerWriter.open(ledger, "0.1.0")

    # Baseline
    baseline_payload = {
        "kind": "external_eval",
        "severity": "info",
        "tier": "external",
        "track": "test-track",
        "condition": "base",
        "model": "Qwen/Qwen3-0.6B",
        "sha256": "0" * 64,
        "tool": "lm-eval",
        "n_samples": {"bench-name": 1000},
        "metrics": {"bench-name": {"acc,none": 0.40, "acc_stderr,none": 0.01}},
    }
    w.append("audit", "auditor", baseline_payload, epoch=0, night=1)

    # Candidate
    candidate_payload = {
        "kind": "external_eval",
        "severity": "info",
        "tier": "external",
        "track": "test-track",
        "condition": "adapter:c-0001",
        "model": "Qwen/Qwen3-0.6B",
        "sha256": "1" * 64,
        "tool": "lm-eval",
        "n_samples": {"bench-name": 1000},
        "metrics": {"bench-name": {"acc,none": 0.50, "acc_stderr,none": 0.01}},
    }
    w.append("audit", "auditor", candidate_payload, epoch=1, night=1)

    result = _invoke("objective", "progress", "test-obj", "--root", str(tmp_path))
    assert result.exit_code == 0
    # Should show baseline
    assert "baseline" in result.stdout
    assert "0.4000" in result.stdout
    # Should show current
    assert "current" in result.stdout
    assert "0.5000" in result.stdout
    # Should show change
    assert "change" in result.stdout or "0.1000" in result.stdout or "+0.1" in result.stdout


def test_recipes_lists_entries_and_availability(tmp_path: Path, monkeypatch) -> None:
    """recipes command lists entries and marks availability."""
    # Create a minimal recipe library
    lib_json = tmp_path / "library.json"
    lib_json.write_text(
        json.dumps(
            {
                "version": 1,
                "recipes": [
                    {
                        "id": "finetune-lora",
                        "capability": "finetune",
                        "title": "LoRA Fine-tuning",
                        "skill": "nemo-mbridge-perf",
                        "summary": "LoRA fine-tuning recipe",
                        "source": "NVIDIA NeMo",
                    },
                    {
                        "id": "evaluate-gsm8k",
                        "capability": "evaluate",
                        "title": "GSM8K Evaluation",
                        "skill": "huggingface-llm-trainer",
                        "summary": "Evaluate on GSM8K",
                        "source": "HuggingFace",
                    },
                ],
            }
        )
    )

    # Create skills directory with only one skill present
    skills_dir = tmp_path / "skills"
    (skills_dir / "nemo-mbridge-perf").mkdir(parents=True)

    # Set PRAVRUDHI_SKILL_DIRS to point to our temporary skills directory
    monkeypatch.setenv("PRAVRUDHI_SKILL_DIRS", str(skills_dir))

    # Monkey-patch the recipes module to use our test library
    from pravrudhi.application import recipes as recipes_module

    original_library = recipes_module.library

    def mock_library(path=None):
        return original_library(lib_json)

    def mock_skill_dirs():
        return (skills_dir,)

    monkeypatch.setattr(recipes_module, "library", mock_library)
    monkeypatch.setattr(recipes_module, "skill_dirs", mock_skill_dirs)

    result = _invoke("recipes", "--root", str(tmp_path))
    assert result.exit_code == 0
    # Should list entries
    assert "finetune-lora" in result.stdout
    assert "evaluate-gsm8k" in result.stdout
    # Should mark availability
    assert "available" in result.stdout
    assert "not installed" in result.stdout
    # The skill we created should be marked as available
    assert result.stdout.count("available") >= 1
    # The skill we didn't create should be marked as not installed
    assert result.stdout.count("not installed") >= 1


def test_recipes_filter_by_capability(tmp_path: Path, monkeypatch) -> None:
    """recipes command can filter by capability."""
    lib_json = tmp_path / "library.json"
    lib_json.write_text(
        json.dumps(
            {
                "version": 1,
                "recipes": [
                    {
                        "id": "finetune-lora",
                        "capability": "finetune",
                        "title": "LoRA Fine-tuning",
                        "skill": "s1",
                        "summary": "",
                        "source": "",
                    },
                    {
                        "id": "evaluate-gsm8k",
                        "capability": "evaluate",
                        "title": "GSM8K Evaluation",
                        "skill": "s2",
                        "summary": "",
                        "source": "",
                    },
                ],
            }
        )
    )

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    from pravrudhi.application import recipes as recipes_module

    original_library = recipes_module.library

    def mock_library(path=None):
        return original_library(lib_json)

    monkeypatch.setattr(recipes_module, "library", mock_library)
    monkeypatch.setattr(recipes_module, "skill_dirs", lambda: (skills_dir,))

    result = _invoke("recipes", "--capability", "finetune", "--root", str(tmp_path))
    assert result.exit_code == 0
    assert "finetune-lora" in result.stdout
    # The evaluate recipe should not appear when filtering by finetune
    assert "evaluate-gsm8k" not in result.stdout


def test_objective_list_shows_multiple_objectives(tmp_path: Path) -> None:
    """objective list shows all objectives with their track and intent."""
    obj_dir = tmp_path / ".pravrudhi" / "objectives"
    obj_dir.mkdir(parents=True)

    # Create multiple objectives
    obj1 = {
        "intent": "improve accuracy on GSM8K",
        "track": "model",
        "benchmarks": [{"id": "gsm8k", "tool": "lm-eval", "metric": "exact_match,strict-match"}],
    }
    obj2 = {
        "intent": "improve MBPP+ pass rate",
        "track": "harness",
        "benchmarks": [{"id": "mbpp", "tool": "evalplus", "metric": "pass@1"}],
    }

    (obj_dir / "gsm8k-goal.yaml").write_text(yaml.dump(obj1))
    (obj_dir / "mbpp-goal.yaml").write_text(yaml.dump(obj2))

    result = _invoke("objective", "list", "--root", str(tmp_path))
    assert result.exit_code == 0
    assert "gsm8k-goal" in result.stdout
    assert "mbpp-goal" in result.stdout
    assert "[model]" in result.stdout
    assert "[harness]" in result.stdout
    assert "no objectives yet" not in result.stdout


def test_objective_new_with_target_delta(tmp_path: Path) -> None:
    """objective new with --target-delta creates an objective with a target."""
    result = _invoke(
        "objective",
        "new",
        "my-model",
        "--intent", "improve accuracy",
        "--track", "model",
        "--metric", "acc,none",
        "--target-delta", "0.05",
        "--root", str(tmp_path),
    )
    assert result.exit_code == 0

    obj_file = tmp_path / ".pravrudhi" / "objectives" / "my-model.yaml"
    assert obj_file.exists()
    obj = yaml.safe_load(obj_file.read_text())
    assert obj["target_delta"] == 0.05


def test_objective_show_displays_objective_as_json(tmp_path: Path) -> None:
    """objective show returns objective and its progress as JSON."""
    obj_dir = tmp_path / ".pravrudhi" / "objectives"
    obj_dir.mkdir(parents=True)
    obj = {
        "intent": "test objective",
        "track": "test",
        "benchmarks": [{"id": "bench", "tool": "lm-eval", "metric": "acc,none"}],
    }
    (obj_dir / "test-obj.yaml").write_text(yaml.dump(obj))

    result = _invoke("objective", "show", "test-obj", "--root", str(tmp_path))
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["id"] == "test-obj"
    assert data["intent"] == "test objective"
    assert data["track"] == "test"
    assert "progress" in data


def test_objective_with_custom_tool(tmp_path: Path) -> None:
    """objective new can use evalplus as the tool."""
    result = _invoke(
        "objective",
        "new",
        "mbpp-goal",
        "--intent", "improve MBPP+ pass rate",
        "--track", "harness",
        "--metric", "pass@1",
        "--tool", "evalplus",
        "--root", str(tmp_path),
    )
    assert result.exit_code == 0

    obj_file = tmp_path / ".pravrudhi" / "objectives" / "mbpp-goal.yaml"
    assert obj_file.exists()
    obj = yaml.safe_load(obj_file.read_text())
    assert obj["benchmarks"][0]["tool"] == "evalplus"
