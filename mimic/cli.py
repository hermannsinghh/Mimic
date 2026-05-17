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
@click.option("--model", "-m", default="gpt-4o", show_default=True,
              help="LLM model to use for orchestration.")
@click.option("--no-cache", is_flag=True, default=False,
              help="Skip cache and re-fetch all data.")
def simulate(ticker: str, event: str, severity: float, model: str, no_cache: bool):
    """Simulate how TICKER would respond to EVENT."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

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
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    from rich.console import Console
    from rich.pretty import pprint
    from mimic import Twin

    console = Console()
    twin = Twin.from_ticker(ticker)
    console.print(f"\n[bold]{twin.context.name} ({twin.context.ticker})[/bold]")
    console.print(twin.context.summary())
    pprint(twin.context.model_dump())
