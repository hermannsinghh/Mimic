"""CLI for Mimic — mimic simulate WMT "China port closes"."""
from __future__ import annotations
import click


@click.group()
def cli():
    """Mimic — LLM-based digital twins for public companies."""
    pass


@cli.command()
@click.argument("ticker")
@click.argument("event")
@click.option("--severity", "-s", default=0.7, show_default=True,
              type=click.FloatRange(0.0, 1.0), help="Event severity 0-1.")
@click.option("--model", "-m", default=None,
              help="LLM model (default: deepseek-chat or gpt-4o from env).")
@click.option("--no-cache", is_flag=True, default=False,
              help="Skip cache and re-fetch all data.")
def simulate(ticker: str, event: str, severity: float, model: str | None, no_cache: bool):
    """Simulate how TICKER would respond to EVENT."""
    from mimic.llm import load_mimic_env, default_chat_model

    load_mimic_env()
    if model is None:
        model = default_chat_model()

    from rich.console import Console
    from mimic import Twin

    console = Console()

    try:
        twin = Twin.from_ticker(ticker, use_cache=not no_cache)
        console.print(f"[green]✓ Computed economic formulas[/green]")

        console.print(f"[cyan]→ Running orchestrator ({model})...[/cyan]")
        result = twin.simulate(event, severity=severity, model=model)
        console.print(f"[green]✓ Ran orchestrator ({model})[/green]")

        console.print(result.pretty())
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@cli.command()
@click.argument("ticker")
def context(ticker: str):
    """Show the full CompanyContext for TICKER."""
    from mimic.llm import load_mimic_env

    load_mimic_env()

    from rich.console import Console
    from rich.pretty import pprint
    from mimic import Twin

    console = Console()
    twin = Twin.from_ticker(ticker)
    console.print(f"\n[bold]{twin.context.name} ({twin.context.ticker})[/bold]")
    console.print(twin.context.summary())
    pprint(twin.context.model_dump())


@cli.group()
def scenario():
    """Scenario operations — pack, verify, inspect, sign."""


@scenario.command("inspect")
@click.argument("scenario_dir", type=click.Path(exists=True, file_okay=False))
def scenario_inspect(scenario_dir: str):
    """Load a scenario directory, validate apiVersion mimic.scenario/v1, print summary."""
    from pathlib import Path

    from rich.console import Console
    from rich.table import Table

    from mimic.framework.scenario import load_spec

    console = Console()
    spec = load_spec(Path(scenario_dir) / "scenario.yaml")
    meta = spec.metadata
    body = spec.spec
    table = Table(show_header=False)
    table.add_row("name", meta.name)
    table.add_row("version", meta.version)
    table.add_row("license", meta.license)
    table.add_row("author DID", meta.author_did)
    table.add_row("mimic version", meta.mimic_version)
    table.add_row("event IRI", str(body.event.iri))
    table.add_row("event duration (d)", str(body.event.duration_days))
    table.add_row("tiers", ",".join(body.scope.tiers))
    table.add_row("MC paths", str(body.mc.paths))
    table.add_row("MC horizon (d)", str(body.mc.horizon_days))
    table.add_row("seed_global", hex(body.mc.seed_global))
    table.add_row("budget USD", str(body.budget_usd))
    console.print(table)


@scenario.command("pack")
@click.argument("scenario_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--out", "-o", required=True, type=click.Path(),
              help="Output tarball path.")
def scenario_pack(scenario_dir: str, out: str):
    """Pack a scenario directory into a content-addressed tar."""
    from rich.console import Console

    from mimic.framework.scenario import pack

    console = Console()
    manifest = pack(scenario_dir, out)
    console.print(f"[green]✓ packed {manifest.name} v{manifest.version}[/green]")
    console.print(f"  files:    {len(manifest.files)}")
    console.print(f"  out:      {out}")
    console.print(f"  digest:   sha256:{manifest.artifact_sha256}")


@scenario.command("verify")
@click.argument("artifact_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--expected-digest", "-d", required=True,
              help="Expected artifact_sha256 digest (without sha256: prefix).")
@click.option("--unpack-to", "-u", required=True, type=click.Path(),
              help="Destination directory to unpack into.")
def scenario_verify(artifact_path: str, expected_digest: str, unpack_to: str):
    """Unpack ARTIFACT_PATH and verify it matches EXPECTED_DIGEST."""
    from rich.console import Console

    from mimic.framework.scenario import ArtifactVerificationError, unpack

    console = Console()
    expected_digest = expected_digest.removeprefix("sha256:")
    try:
        manifest = unpack(artifact_path, unpack_to, expected_digest=expected_digest)
    except ArtifactVerificationError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise SystemExit(2)
    console.print(f"[green]✓ verified {manifest.name} v{manifest.version}[/green]")
    console.print(f"  digest matches: sha256:{manifest.artifact_sha256}")


@scenario.command("sign")
@click.argument("artifact_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--signer-did", required=True, help="DID to record as signer.")
@click.option("--key-pem", type=click.Path(),
              help="Ed25519 private key PEM. If omitted, generates an ephemeral key.")
def scenario_sign(artifact_path: str, signer_did: str, key_pem: str | None):
    """Sign an artifact with a local-dev Ed25519 key. NOT audit-grade."""
    import json

    from rich.console import Console

    from mimic.framework.scenario import LocalDevSigner, pack

    console = Console()
    # we sign the digest computed by packing into a sibling .pack.tar so we
    # don't have to re-derive the digest from the artifact_path bytes
    from pathlib import Path
    art = Path(artifact_path)
    if key_pem:
        signer = LocalDevSigner.from_pem(key_pem)
    else:
        signer = LocalDevSigner.generate()
        console.print("[yellow]⚠ generated ephemeral key — public key in signature.metadata[/yellow]")

    # compute the artifact digest by re-packing the unpacked contents
    # (or in the future, by reading a manifest sidecar)
    import hashlib
    digest = hashlib.sha256(art.read_bytes()).hexdigest()
    sig = signer.sign(digest, signer_did=signer_did)
    out = art.with_suffix(art.suffix + ".sig")
    out.write_text(json.dumps(sig.to_dict(), indent=2, sort_keys=True))
    console.print(f"[green]✓ signed {art.name} -> {out.name}[/green]")
    console.print(f"  signer:  {signer_did}")
    console.print(f"  backend: {sig.backend}")
