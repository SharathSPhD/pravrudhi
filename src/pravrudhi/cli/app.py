import json
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
NIGHT_OPT = typer.Option(1, "--night")
BUDGET_OPT = typer.Option(None, "--budget", help="GPU-hours; default from research/prereg/lora_night.yaml")
K_OPT = typer.Option(None, "--k")
TRAIN_PARQUET_OPT = typer.Option(Path(".pravrudhi/data/gsm8k-train.parquet"), "--train-parquet")
GGUF_OPT = typer.Option(None, "--gguf")
CACHE_OPT = typer.Option(Path(".pravrudhi/ext_cache"), "--cache")
LEDGER_OPT = typer.Option(None, "--ledger", help="default <root>/research/ledger.jsonl")
STATE_OPT = typer.Option(None, "--state", help="default <root>/research/state.json")
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
def replay_cmd(
    ledger: Path | None = LEDGER_OPT, state: Path | None = STATE_OPT, verify: bool = VERIFY_OPT, root: Path = ROOT_OPT
) -> None:
    """anusaṁdhāna: rebuild state.json from the ledger alone."""
    ledger = ledger or root / "research" / "ledger.jsonl"
    state = state or root / "research" / "state.json"
    code, lines = replay_command(ledger, state, check=verify)
    for line in lines:
        typer.echo(line, err=code != 0)
    if code:
        raise typer.Exit(code=code)


study_app = typer.Typer(help="Pre-registered studies that write real observe rows.")
pool_app = typer.Typer(help="Seal benchmark pools into the kernel state directory.")
app.add_typer(study_app, name="study")
app.add_typer(pool_app, name="pool")
MODEL_OPT = typer.Option("Qwen/Qwen3-4B", "--model")
POOL_OPT = typer.Option("gsm8k-test", "--bench")
TEMPLATE_OPT = typer.Option(Path("harness/prompts/eval/gsm8k_v1.md"), "--template")


@pool_app.command("seal-gsm8k")
def pool_seal(
    parquet: Path,
    bench: str = POOL_OPT,
    root: Path = ROOT_OPT,
    offset: int = typer.Option(0, "--offset"),
    count: int | None = typer.Option(None, "--count"),
) -> None:
    from pravrudhi.application.pool_admin import seal_gsm8k

    m = seal_gsm8k(root, parquet, bench, offset=offset, count=count)
    typer.echo(f"sealed {m['bench']}: {m['n_items']} items, pool_version {m['pool_version'][:16]}")


@pool_app.command("seal-mbppplus")
def pool_seal_mbpp(root: Path = ROOT_OPT, cache: Path = CACHE_OPT) -> None:
    """Seal EvalPlus MBPP+ as a kernel pool (hidden tests executed only inside the sandbox)."""
    from pravrudhi.application.pool_admin import seal_mbpp_plus

    m = seal_mbpp_plus(root, cache)
    typer.echo(f"sealed {m['bench']}: {m['n_items']} items, pool_version {m['pool_version'][:16]}")


@app.command("preflight")
def preflight_cmd(
    model: str = MODEL_OPT,
    bench: str = POOL_OPT,
    template: Path = TEMPLATE_OPT,
    root: Path = ROOT_OPT,
    n_items: int = typer.Option(32, "--n-items"),
    batch_size: int = typer.Option(16, "--batch-size"),
) -> None:
    """Measure peak VRAM and tokens/s on this card with one real job; write
    research/prereg/measured_stack.json."""
    from pravrudhi.application.preflight import preflight

    out = preflight(
        root,
        model=model,
        bench_pool=root / ".pravrudhi" / "kernel" / "pools" / bench,
        template=template,
        n_items=n_items,
        batch_size=batch_size,
    )
    for k in (
        "gpu",
        "image_digest",
        "peak_gib_torch_allocated",
        "peak_gib_nvidia_smi",
        "tok_s_batched",
        "load_s",
        "gen_s",
    ):
        typer.echo(f"{k}: {out[k]}")


@study_app.command("noise-floor")
def study_noise_floor(
    model: str = MODEL_OPT,
    bench: str = POOL_OPT,
    template: Path = TEMPLATE_OPT,
    root: Path = ROOT_OPT,
    rotations: int = typer.Option(10, "--rotations"),
    seeds: int = typer.Option(3, "--seeds"),
    k: int = typer.Option(100, "--k"),
    exposure_cap: int = typer.Option(3, "--exposure-cap"),
    temperature: float = typer.Option(0.7, "--temperature"),
    max_new_tokens: int = typer.Option(512, "--max-new-tokens"),
    batch_size: int = typer.Option(16, "--batch-size"),
    night: int = typer.Option(0, "--night"),
) -> None:
    """R rotations x S seeds of the unmodified trainee, each a real kernel-scored observe row; writes
    variance.json."""
    from pravrudhi.application.noise_floor import noise_floor

    var = noise_floor(
        root,
        model=model,
        pool_dir=root / ".pravrudhi" / "kernel" / "pools" / bench,
        template=template,
        rotations=rotations,
        seeds=seeds,
        k=k,
        exposure_cap=exposure_cap,
        temperature=temperature,
        max_new_tokens=max_new_tokens,
        batch_size=batch_size,
        night=night,
        log=typer.echo,
    )
    typer.echo(
        f"n_runs={var['n_runs']} mean={var['mean_pass_rate']:.4f} wilson={var['wilson_95']} "
        f"sigma_seed={var['sigma_seed']:.4f} sigma_rot={var['sigma_rot']:.4f}"
    )


@app.command("evidence")
def evidence_cmd(
    name: str = typer.Argument("noise_floor"),
    root: Path = ROOT_OPT,
    check: bool = typer.Option(False, "--check", help="Compare with the committed document; exit 1 on any difference."),
) -> None:
    """Render docs/evidence/<name>.md from the ledger alone (make reproduce)."""
    from pravrudhi.application.evidence import render_first_night, render_nights_summary, render_noise_floor

    if name == "noise_floor":
        text = render_noise_floor(root / "research" / "ledger.jsonl", root / "research" / "prereg" / "variance.json")
        dest = root / "docs" / "evidence" / "L3_noise_floor.md"
    elif name == "summary":
        text = render_nights_summary(root / "research" / "ledger.jsonl", (1, 2))
        dest = root / "docs" / "evidence" / "L4_summary.json"
    elif name.startswith("summary"):
        nights = tuple(int(x) for x in name.removeprefix("summary").split("-") if x)
        text = render_nights_summary(root / "research" / "ledger.jsonl", nights)
        dest = root / "docs" / "evidence" / f"P1_summary_{'_'.join(str(n) for n in nights)}.json"
    elif name == "external":
        from pravrudhi.application.external import render_external

        text = render_external(root / "research" / "ledger.jsonl")
        dest = root / "docs" / "evidence" / "P1_external.md"
    elif name.startswith("night"):
        text = render_first_night(root / "research" / "ledger.jsonl", int(name.removeprefix("night") or "1"))
        dest = root / "docs" / "evidence" / f"L4_{name}.md"
    else:
        typer.echo(f"unknown evidence document {name}", err=True)
        raise typer.Exit(code=2)
    if check:
        if not dest.exists() or dest.read_text() != text:
            typer.echo(f"DIFFERS: {dest}", err=True)
            raise typer.Exit(code=1)
        typer.echo(f"reproduced {dest} byte-identically")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text)
    typer.echo(f"wrote {dest}")


@app.command("night")
def night_cmd(
    night: int = NIGHT_OPT,
    budget: float | None = BUDGET_OPT,
    k: int | None = K_OPT,
    root: Path = ROOT_OPT,
    train_parquet: Path = TRAIN_PARQUET_OPT,
    gguf: Path | None = GGUF_OPT,
) -> None:
    """Run one budgeted night: propose -> deliberate -> execute -> dispose. Every observation is kernel-scored."""
    from pravrudhi.application.night import run_night
    from pravrudhi.application.spine import resolve_model_snapshot

    if gguf is None:
        import yaml

        cfg = yaml.safe_load((root / "research" / "prereg" / "lora_night.yaml").read_text())
        gguf = resolve_model_snapshot("Qwen/Qwen3-30B-A3B-GGUF") / str(cfg["proposer"]["gguf"])
    out = run_night(root, night=night, budget_gpu_h=budget, k=k, train_parquet=train_parquet, gguf=gguf, log=typer.echo)
    typer.echo(json.dumps(out, indent=2))


@app.command("inbox")
def inbox_cmd(root: Path = ROOT_OPT) -> None:
    """List promotion packs awaiting the operator (badge from replay; nothing here is hand-set)."""
    from pravrudhi.application.night import inbox_listing

    rows = inbox_listing(root)
    if not rows:
        typer.echo("inbox empty")
    for r in rows:
        typer.echo(f"{r['night']} {r['candidate']} badge={r['badge']} signed={r['signed']} {r['pack']}")


@app.command("init")
def init_cmd(root: Path = ROOT_OPT, model: str | None = typer.Option(None, "--model")) -> None:
    """Make this project ready for a night: kernel state dir, config, pre-registrations, prompts, genesis ledger."""
    from pravrudhi.application.init import init_project

    out = init_project(root, model=model)
    typer.echo(f"initialised {out['root']} (isolation {out['isolation']}); created {len(out['created'])} files")
    for c in out["created"]:
        typer.echo(f"  {c}")


@app.command("status")
def status_cmd(root: Path = ROOT_OPT) -> None:
    """What the ledger says: chain, candidates, badges, nights, inbox."""
    from pravrudhi.application.status import status

    typer.echo(json.dumps(status(root), indent=2, sort_keys=True))


@app.command("export")
def export_cmd(dest: Path, candidate: str | None = typer.Option(None, "--candidate"), root: Path = ROOT_OPT) -> None:
    """Copy the promoted (green) adapter and its provenance manifest to DEST. Never merges into base weights."""
    from pravrudhi.application.export import export_adapter

    m = export_adapter(root, dest, candidate_id=candidate)
    typer.echo(f"exported {m['candidate_id']} (night {m['night']}, adapter {m['adapter_sha256'][:12]}) to {dest}")


@app.command("serve")
def serve_cmd(
    root: Path = ROOT_OPT, host: str = typer.Option("127.0.0.1", "--host"), port: int = typer.Option(8765, "--port")
) -> None:
    """Serve the ledger, candidates, observations, evidence and inbox over HTTP (sign-off needs an operator header)."""
    from pravrudhi.api.server import serve

    serve(root, host=host, port=port)


@study_app.command("paired-confirm")
def study_paired_confirm(
    night: int = typer.Option(1, "--night"),
    candidate: str | None = typer.Option(None, "--candidate"),
    seed: int = typer.Option(7, "--seed"),
    k: int = typer.Option(100, "--k"),
    root: Path = ROOT_OPT,
) -> None:
    """Incumbent adapter vs baseline on a fresh rotation, per-item paired; Hedges g with BCa CI and a permutation p."""
    from pravrudhi.application.confirm_eval import paired_confirm

    paired_confirm(root, night=night, candidate_id=candidate, seed=seed, k=k, log=typer.echo)


@study_app.command("harness-noise-floor")
def study_harness_nf(
    rotations: int = typer.Option(3, "--rotations"),
    seeds: int = typer.Option(3, "--seeds"),
    k: int = typer.Option(100, "--k"),
    night: int = typer.Option(0, "--night"),
    root: Path = ROOT_OPT,
) -> None:
    """A/A of the baseline harness on MBPP+ (kernel-scored hidden tests); writes research/prereg/variance_harness.json."""
    from pravrudhi.application.harness_track import harness_noise_floor

    out = harness_noise_floor(root, rotations=rotations, seeds=seeds, k=k, night=night, log=typer.echo)
    typer.echo(json.dumps({k2: out[k2] for k2 in ("n_runs", "mean_plus_pass", "sigma_seed", "sigma_rot")}))


@app.command("harness-night")
def harness_night_cmd(
    night: int = NIGHT_OPT,
    budget: float | None = BUDGET_OPT,
    k: int | None = K_OPT,
    root: Path = ROOT_OPT,
    gguf: Path | None = GGUF_OPT,
) -> None:
    """Track H night: fixed model, mutable harness, paired on MBPP+ rotations, hidden tests scored in the sandbox."""
    from pravrudhi.application.harness_track import run_harness_night
    from pravrudhi.application.spine import resolve_model_snapshot

    if gguf is None:
        import yaml

        cfg = yaml.safe_load((root / "research" / "prereg" / "harness_night.yaml").read_text())
        gguf = resolve_model_snapshot("Qwen/Qwen3-30B-A3B-GGUF") / str(cfg["proposer"]["gguf"])
    typer.echo(json.dumps(run_harness_night(root, night=night, k=k, budget_gpu_h=budget, gguf=gguf, log=typer.echo), indent=2))


def main() -> None:
    app()


@app.command("ext-record")
def ext_record_cmd(
    path: Path = typer.Argument(..., help="lm-eval results.json or EvalPlus *_eval_results.json"),
    tool: str = typer.Option(..., "--tool", help="lm-eval | evalplus"),
    track: str = typer.Option(..., "--track", help="M (model) | H (harness)"),
    condition: str = typer.Option(..., "--condition", help="base | adapter:c-0045 | harness:c-0012"),
    model: str = typer.Option(..., "--model"),
    night: int = typer.Option(0, "--night"),
    dataset: str = typer.Option("", "--dataset", help="EvalPlus dataset: humaneval | mbpp"),
    seed: int | None = typer.Option(None, "--seed"),
    root: Path = ROOT_OPT,
) -> None:
    """Admit an external scorer's result file into the ledger by hash (tier: external)."""
    from pravrudhi.application.external import record_external

    row = record_external(root, path.resolve(), tool=tool, track=track, condition=condition, model=model,
                          night=night, dataset=dataset, seed=seed)
    typer.echo(json.dumps({k: row[k] for k in ("seq", "track", "condition", "metrics", "sha256")}))
