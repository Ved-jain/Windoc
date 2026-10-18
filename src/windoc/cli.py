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
from windoc.repairs import RepairStatus, execute_repair, registry

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

    if primary.cause_id.endswith("_ALL_HEALTHY"):
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

        from windoc.repairs import registry
        matching_repairs = registry.find_for_cause(primary.cause_id)
        if matching_repairs:
            rep_list = "\n".join(
                f" - [bold cyan]windoc repair {r.repair_id}[/bold cyan] ({r.name}, Risk: {r.risk_level.value})"
                for r in matching_repairs
            )
            content += f"\n\n[bold green]Available Controlled Repairs:[/bold green]\n{rep_list}"

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
    from windoc.core.engine import evaluate_bluetooth_hypotheses, evaluate_network_hypotheses
    from windoc.domains.bluetooth import run_all_bluetooth_checks

    console.print("[bold cyan]Starting comprehensive diagnostic scan...[/bold cyan]\n")

    # 1. Network Subsystem
    with console.status("[bold green]Analyzing network subsystem...[/bold green]"):
        net_results = run_all_network_checks()
    render_diagnostic_results("Network Diagnostics", net_results)
    net_report = evaluate_network_hypotheses(net_results)
    render_diagnosis_report(net_report)

    console.print()

    # 2. Bluetooth Subsystem
    with console.status("[bold green]Analyzing Bluetooth subsystem...[/bold green]"):
        bth_results = run_all_bluetooth_checks()
    render_diagnostic_results("Bluetooth Diagnostics", bth_results)
    bth_report = evaluate_bluetooth_hypotheses(bth_results)
    render_diagnosis_report(bth_report)


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


@diagnose_app.command(name="bluetooth")
def diagnose_bluetooth() -> None:
    """Diagnose Bluetooth controller hardware, services, and paired accessories."""
    from windoc.core.engine import evaluate_bluetooth_hypotheses
    from windoc.domains.bluetooth import run_all_bluetooth_checks

    console.print("[bold cyan]Investigating Bluetooth subsystem...[/bold cyan]\n")
    with console.status("[bold green]Executing Bluetooth checks...[/bold green]"):
        results = run_all_bluetooth_checks()
    render_diagnostic_results("Bluetooth Diagnostic Report", results)

    report = evaluate_bluetooth_hypotheses(results)
    render_diagnosis_report(report)


@app.command(name="list-repairs")
def list_repairs() -> None:
    """List approved repair procedures in the controlled repair registry."""
    table = Table(title="Controlled Repair Registry", border_style="cyan")
    table.add_column("Repair ID", style="bold cyan", no_wrap=True)
    table.add_column("Name", style="bold white")
    table.add_column("Risk", justify="center")
    table.add_column("Admin", justify="center")
    table.add_column("Target Cause", style="dim")
    table.add_column("Expected Effects", style="white")

    for rep in registry.list_all():
        risk_badge = f"[green]{rep.risk_level.value}[/green]" if rep.risk_level.value == "LOW" else f"[yellow]{rep.risk_level.value}[/yellow]"
        admin_badge = "[red]Yes[/red]" if rep.requires_admin else "[green]No[/green]"
        table.add_row(
            rep.repair_id,
            rep.name,
            risk_badge,
            admin_badge,
            rep.target_cause_id,
            rep.expected_effects,
        )

    console.print(table)


@app.command(name="repair")
def repair_cmd(
    repair_id: str = typer.Argument(..., help="The identifier of the repair to execute (e.g. net.flush_dns)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive confirmation prompt"),
) -> None:
    """Execute a controlled repair procedure with pre/post verification."""
    rep = registry.get(repair_id)
    if not rep:
        console.print(f"[bold red]Error:[/bold red] Unknown repair '{repair_id}'. Run `windoc list-repairs` to see all supported repairs.")
        raise typer.Exit(code=1)

    result = execute_repair(rep, auto_approve=yes)

    if result.status == RepairStatus.SUCCESS:
        console.print(
            Panel(
                f"[bold green][OK] Repair Succeeded and Independently Verified![/bold green]\n\n"
                f"[white]{result.message}[/white]",
                title="[bold green]Repair Verification: SUCCESS[/bold green]",
                border_style="green",
            )
        )
    elif result.status == RepairStatus.VERIFICATION_FAILED:
        console.print(
            Panel(
                f"[bold red][!] Command executed, but independent verification failed.[/bold red]\n\n"
                f"[white]{result.message}[/white]\n\n"
                f"[yellow]The original symptom was not resolved by this procedure.[/yellow]",
                title="[bold red]Repair Verification: FAILED[/bold red]",
                border_style="red",
            )
        )
    elif result.status == RepairStatus.PERMISSION_DENIED:
        console.print(
            Panel(
                f"[bold yellow][!] Administrator Privileges Required[/bold yellow]\n\n"
                f"[white]{result.message}[/white]",
                title="[bold yellow]Permission Denied[/bold yellow]",
                border_style="yellow",
            )
        )
    elif result.status == RepairStatus.ABORTED:
        console.print("[yellow]Repair cancelled by user.[/yellow]")
    else:
        console.print(
            Panel(
                f"[bold red][!] Repair execution failed.[/bold red]\n\n"
                f"[white]{result.message}[/white]",
                title="[bold red]Repair Failed[/bold red]",
                border_style="red",
            )
        )


@app.command()
def list_domains() -> None:
    """List diagnostic domains supported or planned by WinDoc."""
    table = Table(title="Diagnostic Domains", border_style="cyan")
    table.add_column("Domain", style="bold yellow")
    table.add_column("Status", style="green")
    table.add_column("Description", style="white")

    table.add_row("network", "Supported (Active)", "Wi-Fi, Ethernet, IP config, Gateway, DNS, Connectivity")
    table.add_row("bluetooth", "Supported (Active)", "Adapter state, service, device connection")
    table.add_row("drivers", "Planned (Milestone 7)", "Device Manager error codes, missing devices")
    table.add_row("update", "Planned (Milestone 8)", "Windows Update services, error codes, logs")
    table.add_row("system", "Planned (Milestone 9)", "System file integrity, component store, services")
    table.add_row("performance", "Planned (Milestone 10)", "CPU, RAM, disk utilization, resource spikes")

    console.print(table)


@app.command()
def activate() -> None:
    """Register WinDoc globally in Windows so you never need to activate a venv."""
    from pathlib import Path

    user_home = Path.home()
    local_bin = user_home / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)

    # Determine windoc executable path
    venv_windoc = Path(sys.prefix) / "Scripts" / "windoc.exe"
    if not venv_windoc.exists():
        venv_windoc = Path.cwd() / ".venv" / "Scripts" / "windoc.exe"

    if not venv_windoc.exists():
        console.print(
            Panel(
                f"[bold red][FAIL] Could not locate windoc.exe binary.[/bold red]\n\n"
                f"Searched in: {sys.prefix}\\Scripts and {Path.cwd()}\\.venv\\Scripts",
                title="Activation Failed",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    # Write global stubs to ~/.local/bin
    cmd_stub = local_bin / "windoc.cmd"
    cmd_content = f'@echo off\n"{venv_windoc}" %*\n'
    cmd_stub.write_text(cmd_content, encoding="utf-8")

    ps1_stub = local_bin / "windoc.ps1"
    ps1_content = f'& "{venv_windoc}" @args\n'
    ps1_stub.write_text(ps1_content, encoding="utf-8")

    # Ensure ~/.local/bin is in User Environment PATH
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            current_path, _ = winreg.QueryValueEx(key, "Path")
            path_parts = [p.strip() for p in current_path.split(";") if p.strip()]
            str_local_bin = str(local_bin)
            if str_local_bin.lower() not in [p.lower() for p in path_parts]:
                new_path = f"{str_local_bin};{current_path}"
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
    except Exception:
        pass

    console.print(
        Panel(
            f"[bold green][OK] WinDoc is now globally active and registered![/bold green]\n\n"
            f"[cyan]Target executable:[/cyan] {venv_windoc}\n"
            f"[cyan]Global launcher:[/cyan]   {cmd_stub}\n"
            f"[cyan]PowerShell stub:[/cyan]   {ps1_stub}\n\n"
            f"[bold white]You can now run [green]windoc[/green] directly from ANY terminal or directory without manually activating any virtual environment.[/bold white]",
            title="[bold green]WinDoc Activation: Ready[/bold green]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    app()
