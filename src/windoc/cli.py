"""Command-line interface for WinDoc."""

import platform
import sys
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from windoc import __version__
from windoc.core.models import CheckStatus, DiagnosticResult
from windoc.domains.network import run_all_network_checks

app = typer.Typer(
    name="windoc",
    help="Evidence-driven Windows diagnostics and repair CLI.",
    add_completion=False,
    no_args_is_help=True,
)
diagnose_app = typer.Typer(
    name="diagnose",
    help="Run targeted diagnostic checks for specific Windows subsystems.",
    add_completion=False,
    no_args_is_help=True,
)
app.add_typer(diagnose_app, name="diagnose")
console = Console()


def version_callback(value: bool) -> None:
    """Print the version and exit."""
    if value:
        console.print(f"[bold cyan]WinDoc[/bold cyan] version [green]{__version__}[/green]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """WinDoc: Local, evidence-driven Windows troubleshooting tool."""


def render_diagnostic_results(title: str, results: List[DiagnosticResult]) -> None:
    """Render a list of diagnostic results into a formatted Rich table."""
    table = Table(title=title, border_style="cyan", show_lines=True)
    table.add_column("Status", style="bold", width=8, justify="center")
    table.add_column("Check ID", style="cyan", min_width=26, no_wrap=True)
    table.add_column("Observation", style="white")
    table.add_column("Source", style="dim", min_width=16)

    pass_count = 0
    fail_count = 0
    warn_count = 0
    err_count = 0

    for res in results:
        if res.status == CheckStatus.PASS:
            status_badge = "[bold green]PASS[/bold green]"
            pass_count += 1
        elif res.status == CheckStatus.FAIL:
            status_badge = "[bold red]FAIL[/bold red]"
            fail_count += 1
        elif res.status == CheckStatus.WARNING:
            status_badge = "[bold yellow]WARN[/bold yellow]"
            warn_count += 1
        else:
            status_badge = f"[bold magenta]{res.status.value}[/bold magenta]"
            err_count += 1

        table.add_row(
            status_badge,
            res.check_id,
            res.observation,
            res.data_source,
        )

    console.print(table)
    summary = (
        f"[bold]Summary:[/bold] "
        f"[green]{pass_count} Passed[/green] | "
        f"[yellow]{warn_count} Warnings[/yellow] | "
        f"[red]{fail_count} Failed[/red] | "
        f"[magenta]{err_count} Other[/magenta]"
    )
    console.print(Panel(summary, style="cyan", expand=False))


@app.command()
def info() -> None:
    """Display system and environment information."""
    import ctypes

    is_admin = False
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except (AttributeError, OSError):
        pass

    table = Table(title="WinDoc Environment", show_header=False, box=None)
    table.add_column("Property", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("WinDoc Version", __version__)
    table.add_row("Operating System", f"{platform.system()} {platform.release()} ({platform.version()})")
    table.add_row("Architecture", platform.machine())
    table.add_row("Python Version", sys.version.split()[0])
    table.add_row("Administrator Privileges", "[green]Yes[/green]" if is_admin else "[yellow]No (Read-Only)[/yellow]")

    console.print(
        Panel(
            table,
            title="[bold green]System Info[/bold green]",
            border_style="cyan",
            expand=False,
        )
    )


def render_diagnosis_report(report) -> None:
    """Render the evaluated hypothesis verdict and recommended actions."""
    if not report.primary_finding:
        console.print(
            Panel(
                "[bold yellow]Diagnostic findings are inconclusive.[/bold yellow]\n"
                "Insufficient evidence to isolate a single root cause.",
                title="[bold yellow]Investigation Inconclusive[/bold yellow]",
                border_style="yellow",
            )
        )
        return

    primary = report.primary_finding
    conf_pct = int(primary.confidence * 100)

    if primary.cause_id == "NET_ALL_HEALTHY":
        content = (
            f"[bold green][OK] {primary.title}[/bold green] (Confidence: {conf_pct}%)\n\n"
            f"[white]{primary.description}[/white]\n\n"
            f"[bold]Recommended Action:[/bold] {primary.recommended_action}"
        )
        console.print(
            Panel(
                content,
                title="[bold green]Root Cause Diagnosis[/bold green]",
                border_style="green",
            )
        )
    else:
        evidence_text = "\n".join(f" - {ev}" for ev in primary.supporting_evidence) or " - Correlated failure symptoms"
        content = (
            f"[bold red][!] Root Cause:[/bold red] [bold white]{primary.title}[/bold white] (Confidence: [bold red]{conf_pct}%[/bold red])\n"
            f"[dim]Status: {primary.status.value}[/dim]\n\n"
            f"[white]{primary.description}[/white]\n\n"
            f"[bold cyan]Supporting Evidence:[/bold cyan]\n{evidence_text}\n\n"
            f"[bold yellow]Recommended Next Step:[/bold yellow] {primary.recommended_action}"
        )
        console.print(
            Panel(
                content,
                title="[bold red]Root Cause Diagnosis[/bold red]",
                border_style="red",
            )
        )


@app.command()
def scan() -> None:
    """Run an automated diagnostic scan across all supported subsystems."""
    from windoc.core.engine import evaluate_network_hypotheses

    console.print("[bold cyan]Starting comprehensive diagnostic scan...[/bold cyan]\n")
    with console.status("[bold green]Analyzing network subsystem...[/bold green]"):
        results = run_all_network_checks()
    render_diagnostic_results("Network Diagnostics", results)

    report = evaluate_network_hypotheses(results)
    render_diagnosis_report(report)


@diagnose_app.command(name="network")
def diagnose_network() -> None:
    """Diagnose network adapters, IP configuration, gateway, DNS, and external reachability."""
    from windoc.core.engine import evaluate_network_hypotheses

    console.print("[bold cyan]Investigating Network subsystem...[/bold cyan]\n")
    with console.status("[bold green]Executing network checks...[/bold green]"):
        results = run_all_network_checks()
    render_diagnostic_results("Network Diagnostic Report", results)

    report = evaluate_network_hypotheses(results)
    render_diagnosis_report(report)


@app.command()
def list_domains() -> None:
    """List diagnostic domains supported or planned by WinDoc."""
    table = Table(title="Diagnostic Domains", border_style="cyan")
    table.add_column("Domain", style="bold yellow")
    table.add_column("Status", style="green")
    table.add_column("Description", style="white")

    table.add_row("network", "Supported (Active)", "Wi-Fi, Ethernet, IP config, Gateway, DNS, Connectivity")
    table.add_row("bluetooth", "Planned (Milestone 6)", "Adapter state, service, device connection")
    table.add_row("drivers", "Planned (Milestone 7)", "Device Manager error codes, missing devices")
    table.add_row("update", "Planned (Milestone 8)", "Windows Update services, error codes, logs")
    table.add_row("system", "Planned (Milestone 9)", "System file integrity, component store, services")
    table.add_row("performance", "Planned (Milestone 10)", "CPU, RAM, disk utilization, resource spikes")

    console.print(table)


if __name__ == "__main__":
    app()
