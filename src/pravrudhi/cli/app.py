from pathlib import Path

import typer

from pravrudhi import KERNEL_VERSION, __version__
from pravrudhi.application.gate import check_gate, emit_gate, sign_gate
from pravrudhi.application.replay import replay_command

app = typer.Typer(name="pravrudhi", no_args_is_help=True, help="Recursive self-improvement engine.")
gate_app = typer.Typer(help="Emit, check and sign gate JSON. Gates are never hand-edited.")
contract_app = typer.Typer(help="House alias for `gate check`.")
app.add_typer(gate_app, name="gate")
app.add_typer(contract_app, name="contract")

ROOT_OPT = typer.Option(Path("."), "--root", help="Repository root holding contracts/ and gates/.")
VERSION_OPT = typer.Option(False, "--version")
EVIDENCE_OPT = typer.Option(..., "--evidence")
BY_OPT = typer.Option(..., "--by")
NOTE_OPT = typer.Option("", "--note")
LEDGER_OPT = typer.Option(Path("research/ledger.jsonl"), "--ledger")
STATE_OPT = typer.Option(Path("research/state.json"), "--state")
VERIFY_OPT = typer.Option(
    False,
    "--verify",
    help="Verify the hash chain and compare against the committed state; exit 1 on any difference.",
)


@app.callback(invoke_without_command=True)
def _root(ctx: typer.Context, version: bool = VERSION_OPT) -> None:
    if version:
        typer.echo(f"pravrudhi {__version__} (kernel {KERNEL_VERSION})")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@gate_app.command("emit")
def gate_emit(card_id: str, evidence: Path = EVIDENCE_OPT, root: Path = ROOT_OPT) -> None:
    out = emit_gate(
        card_id,
        contracts_dir=root / "contracts",
        gates_dir=root / "gates",
        evidence_file=evidence,
        kernel_release=KERNEL_VERSION,
    )
    typer.echo(f"wrote {out}")


def _check(path: Path, root: Path) -> None:
    problems = check_gate(path, contracts_dir=root / "contracts")
    if problems:
        for p in problems:
            typer.echo(f"FAIL {p}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"pass {path}")


@gate_app.command("check")
def gate_check(path: Path, root: Path = ROOT_OPT) -> None:
    _check(path, root)


@contract_app.command("check")
def contract_check(path: Path, root: Path = ROOT_OPT) -> None:
    _check(path, root)


@gate_app.command("sign")
def gate_sign(path: Path, by: str = BY_OPT, note: str = NOTE_OPT) -> None:
    sign_gate(path, by=by, note=note)
    typer.echo(f"signed {path} by {by}")


@app.command("replay")
def replay_cmd(ledger: Path = LEDGER_OPT, state: Path = STATE_OPT, verify: bool = VERIFY_OPT) -> None:
    """anusaṁdhāna: rebuild state.json from the ledger alone."""
    code, lines = replay_command(ledger, state, check=verify)
    for line in lines:
        typer.echo(line, err=code != 0)
    if code:
        raise typer.Exit(code=code)


def main() -> None:
    app()
