from pathlib import Path

import pytest
import yaml

from pravrudhi.application.gate import check_gate, emit_gate, sign_gate

CARD = "# L0 — Scaffold\n\n* **Purpose.** x\n"

EVIDENCE = {
    "status": "pass",
    "tier": "smoke",
    "measure_class": "n/a",
    "code_gate": {"verdict": "pass", "evidence": ["make smoke green", "tests=12"]},
    "domain_gate": {"verdict": "pass", "evidence": ["no_claim"]},
    "closure": {
        "technical": {"verdict": "pass", "evidence": ["make smoke green"]},
        "empirical": {"verdict": "pass", "evidence": ["no_claim"]},
        "integrity": {"verdict": "pass", "evidence": ["epoch 0"]},
        "artifacts": {"verdict": "pass", "evidence": ["tree listed"]},
        "memory": {"verdict": "pass", "evidence": ["journal appended"]},
        "signoff": {"verdict": "pending", "evidence": []},
    },
    "hetvabhasa": None,
    "deviations": [],
    "ledger_head": None,
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "contracts").mkdir()
    (tmp_path / "gates").mkdir()
    (tmp_path / "contracts" / "L0_scaffold.md").write_text(CARD)
    (tmp_path / "gates" / "L0.evidence.yaml").write_text(yaml.safe_dump(EVIDENCE))
    return tmp_path


def _emit(repo: Path) -> Path:
    return emit_gate(
        "L0",
        contracts_dir=repo / "contracts",
        gates_dir=repo / "gates",
        evidence_file=repo / "gates" / "L0.evidence.yaml",
        kernel_release="0.1.0",
    )


def test_emit_writes_valid_gate(repo: Path) -> None:
    out = _emit(repo)
    assert out == repo / "gates" / "gate_L0.json"
    assert out.read_text().endswith("\n")
    assert check_gate(out, contracts_dir=repo / "contracts") == []


def test_emit_refuses_unknown_card(repo: Path) -> None:
    with pytest.raises(FileNotFoundError):
        emit_gate(
            "L9",
            contracts_dir=repo / "contracts",
            gates_dir=repo / "gates",
            evidence_file=repo / "gates" / "L0.evidence.yaml",
            kernel_release="0.1.0",
        )


def test_emit_rejects_pruned_without_hetvabhasa(repo: Path) -> None:
    ev = dict(EVIDENCE) | {
        "status": "pruned",
        "code_gate": {"verdict": "pruned", "evidence": ["x"]},
        "domain_gate": {"verdict": "pruned", "evidence": ["x"]},
    }
    (repo / "gates" / "L0.evidence.yaml").write_text(yaml.safe_dump(ev))
    with pytest.raises(ValueError):
        _emit(repo)


def test_check_rejects_no_claim_with_measure_class(repo: Path) -> None:
    ev = dict(EVIDENCE) | {"measure_class": "exploratory"}
    (repo / "gates" / "L0.evidence.yaml").write_text(yaml.safe_dump(ev))
    out = _emit(repo)
    problems = check_gate(out, contracts_dir=repo / "contracts")
    assert any("no_claim" in p for p in problems)


def test_sign_refuses_agent_and_accepts_human(repo: Path) -> None:
    out = _emit(repo)
    with pytest.raises(PermissionError):
        sign_gate(out, by="pravrudhi-agent", note="x")
    sign_gate(out, by="SharathSPhD", note="read")
    text = out.read_text()
    assert '"by": "SharathSPhD"' in text
    assert check_gate(out, contracts_dir=repo / "contracts") == []
