import json
from pathlib import Path

from typer.testing import CliRunner

from pravrudhi.cli.app import app
from pravrudhi_kernel.ledger import LedgerWriter

runner = CliRunner()


def test_replay_writes_then_verifies_then_detects_tamper(tmp_path: Path) -> None:
    ledger = tmp_path / "research" / "ledger.jsonl"
    state = tmp_path / "research" / "state.json"
    w = LedgerWriter.open(ledger, "0.1.0")
    w.append("spend", "executor", {"gpu_h": 0.5}, epoch=0, night=1)
    r = runner.invoke(app, ["replay", "--ledger", str(ledger), "--state", str(state)])
    assert r.exit_code == 0 and state.exists(), r.output
    r = runner.invoke(app, ["replay", "--ledger", str(ledger), "--state", str(state), "--verify"])
    assert r.exit_code == 0 and "matches replay" in r.output
    lines = ledger.read_text().splitlines()
    row = json.loads(lines[1])
    row["payload"]["gpu_h"] = 0.6
    lines[1] = json.dumps(row)
    ledger.write_text("\n".join(lines) + "\n")
    r = runner.invoke(app, ["replay", "--ledger", str(ledger), "--state", str(state), "--verify"])
    assert r.exit_code == 1 and "BROKEN at seq 1" in (r.output + str(r.stderr if hasattr(r, "stderr") else ""))
