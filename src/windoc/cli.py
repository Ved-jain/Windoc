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
            content += (
                f"\n\n[bold green]Ready to Fix:[/bold green] Simply run [bold cyan]windoc fix[/bold cyan] to automatically apply and verify this fix.\n"
                f"[dim](Manual direct command: windoc repair {matching_repairs[0].repair_id})[/dim]"
            )

        console.print(
            Panel(
                content,
                title="[bold red]Root Cause Diagnosis[/bold red]",
                border_style="red",
            )
        )


@app.command()
def scan(
    fix: bool = typer.Option(False, "--fix", "-f", help="Automatically offer to fix any detected issues"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve fixes without confirmation prompts (when using --fix)"),
) -> None:
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

    console.print()

    # 3. Drivers & Hardware Subsystem
    from windoc.core.engine import evaluate_driver_hypotheses
    from windoc.domains.drivers import run_all_driver_checks

    with console.status("[bold green]Analyzing hardware devices & drivers...[/bold green]"):
        drv_results = run_all_driver_checks()
    render_diagnostic_results("Hardware & Driver Diagnostics", drv_results)
    drv_report = evaluate_driver_hypotheses(drv_results)
    render_diagnosis_report(drv_report)

    console.print()

    # 4. Windows Update Subsystem
    from windoc.core.engine import evaluate_update_hypotheses
    from windoc.domains.update import run_all_update_checks

    with console.status("[bold green]Analyzing Windows Update subsystem...[/bold green]"):
        upd_results = run_all_update_checks()
    render_diagnostic_results("Windows Update Diagnostics", upd_results)
    upd_report = evaluate_update_hypotheses(upd_results)
    render_diagnosis_report(upd_report)

    console.print()

    # 5. Windows System Integrity & Core Services
    from windoc.core.engine import evaluate_system_hypotheses
    from windoc.domains.system import run_all_system_checks

    with console.status("[bold green]Analyzing Windows system integrity & core services...[/bold green]"):
        sys_results = run_all_system_checks()
    render_diagnostic_results("Windows System Diagnostics", sys_results)
    sys_report = evaluate_system_hypotheses(sys_results)
    render_diagnosis_report(sys_report)

    console.print()

    # 6. Performance & System Resources
    from windoc.core.engine import evaluate_performance_hypotheses
    from windoc.domains.performance import run_all_performance_checks

    with console.status("[bold green]Analyzing CPU, memory, and disk resources...[/bold green]"):
        perf_results = run_all_performance_checks()
    render_diagnostic_results("Performance & Resource Diagnostics", perf_results)
    perf_report = evaluate_performance_hypotheses(perf_results)
    render_diagnosis_report(perf_report)

    all_reports = [
        (net_report, "Network"),
        (bth_report, "Bluetooth"),
        (drv_report, "Drivers"),
        (upd_report, "Windows Update"),
        (sys_report, "System"),
        (perf_report, "Performance"),
    ]

    has_issues = any(
        r.primary_finding and not r.primary_finding.cause_id.endswith("_ALL_HEALTHY")
        for r, _ in all_reports
    )

    if fix:
        _run_auto_fixes(all_reports, auto_approve=yes)
    elif has_issues:
        is_tty = False
        try:
            is_tty = sys.stdin.isatty()
        except Exception:
            pass
        if is_tty:
            apply_now = typer.confirm(
                "\nWinDoc detected issue(s). Would you like to automatically apply verified fixes now?",
                default=True,
            )
            if apply_now:
                _run_auto_fixes(all_reports, auto_approve=True)
            else:
                console.print("\n[bold cyan]Tip:[/bold cyan] Run [bold green]windoc fix[/bold green] anytime to automatically apply and verify fixes.\n")
        else:
            console.print("\n[bold cyan]Tip:[/bold cyan] Run [bold green]windoc fix[/bold green] to automatically apply and verify fixes.\n")


def _run_auto_fixes(reports, auto_approve: bool = False) -> None:
    """Helper to offer and execute verified fixes for diagnosed issues across domains."""
    from windoc.core.engine import HypothesisStatus

    issues_to_fix = []
    seen_repair_ids = set()

    for report, domain_name in reports:
        # Collect candidate findings, prioritizing primary_finding
        findings_to_check = []
        if report.primary_finding:
            findings_to_check.append(report.primary_finding)
        for f in getattr(report, "all_findings", []):
            if f not in findings_to_check and getattr(f, "status", None) in (HypothesisStatus.CONFIRMED, HypothesisStatus.LIKELY):
                findings_to_check.append(f)

        for finding in findings_to_check:
            if not finding.cause_id.endswith("_ALL_HEALTHY"):
                repairs = registry.find_for_cause(finding.cause_id)
                for rep in repairs:
                    if rep.repair_id not in seen_repair_ids:
                        seen_repair_ids.add(rep.repair_id)
                        issues_to_fix.append((finding, rep, domain_name))

    if not issues_to_fix:
        console.print(
            Panel(
                "[bold green][OK] All scanned subsystems are healthy![/bold green]\n\n"
                "No problems were detected. No repairs are needed.",
                title="[bold green]Scan & Fix: All Good[/bold green]",
                border_style="green",
            )
        )
        return

    console.print(f"\n[bold yellow]WinDoc found {len(issues_to_fix)} issue(s) that can be fixed:[/bold yellow]\n")

    for finding, repair, domain_name in issues_to_fix:
        console.print(
            Panel(
                f"[bold red]Problem Detected:[/bold red] {finding.title}\n"
                f"[white]{finding.description}[/white]\n\n"
                f"[bold cyan]Recommended Fix:[/bold cyan] {repair.name}\n"
                f"[dim]Subsystem: {domain_name} | Procedure ID: {repair.repair_id} | Risk: {repair.risk_level.value}[/dim]\n"
                f"[white]Expected Effect: {repair.expected_effects}[/white]",
                title=f"[bold yellow]Issue: {finding.title}[/bold yellow]",
                border_style="yellow",
            )
        )

        should_apply = auto_approve
        if not should_apply:
            should_apply = typer.confirm(f"Apply fix for '{finding.title}' now?", default=True)

        if not should_apply:
            console.print(f"[dim]Skipped repair: {repair.name}[/dim]\n")
            continue

        result = execute_repair(repair, auto_approve=True)

        if result.status == RepairStatus.SUCCESS:
            console.print(
                Panel(
                    f"[bold green][OK] Fixed and Verified![/bold green]\n\n"
                    f"{result.message}",
                    title="[bold green]Repair Verification: SUCCESS[/bold green]",
                    border_style="green",
                )
            )
        elif result.status == RepairStatus.PERMISSION_DENIED:
            console.print(
                Panel(
                    f"[bold yellow][!] Administrator Privileges Required[/bold yellow]\n\n"
                    f"{result.message}\n\n"
                    f"[white]To apply this fix, open PowerShell or Command Prompt as Administrator and re-run:[/white]\n"
                    f"[bold cyan]windoc fix {domain_name.lower()}[/bold cyan]",
                    title="[bold yellow]Permission Needed[/bold yellow]",
                    border_style="yellow",
                )
            )
        elif result.status == RepairStatus.VERIFICATION_FAILED:
            console.print(
                Panel(
                    f"[bold red][!] Repair executed, but symptoms persist.[/bold red]\n\n"
                    f"{result.message}",
                    title="[bold red]Repair Verification: FAILED[/bold red]",
                    border_style="red",
                )
            )
        else:
            console.print(
                Panel(
                    f"[bold red][!] Repair execution failed.[/bold red]\n\n"
                    f"{result.message}",
                    title="[bold red]Repair Error[/bold red]",
                    border_style="red",
                )
            )


@app.command(name="fix")
def fix_cmd(
    domain: Optional[str] = typer.Argument(
        None,
        help="Optional subsystem domain to fix (network, bluetooth, drivers, update, system, performance). If omitted, scans and fixes all domains.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt and automatically apply fixes"),
) -> None:
    """Zero-hassle one-click repair: scans your PC, finds problems, and applies verified fixes."""
    domain_map = {
        "network": "network",
        "net": "network",
        "bluetooth": "bluetooth",
        "bth": "bluetooth",
        "drivers": "drivers",
        "driver": "drivers",
        "drv": "drivers",
        "update": "update",
        "upd": "update",
        "system": "system",
        "sys": "system",
        "performance": "performance",
        "perf": "performance",
    }

    target_domain = domain_map.get(domain.lower()) if domain else None
    if domain and not target_domain:
        console.print(
            f"[bold red]Error:[/bold red] Unknown domain '{domain}'. "
            f"Supported domains: network, bluetooth, drivers, update, system, performance."
        )
        raise typer.Exit(code=1)

    console.print(
        Panel(
            f"[bold cyan]WinDoc Auto-Fix{' (' + target_domain.capitalize() + ')' if target_domain else ''}[/bold cyan]\n"
            f"Scanning {'subsystem' if target_domain else 'system'} to detect any issues and automatically apply verified fixes...",
            border_style="cyan",
        )
    )

    reports_to_check = []

    if target_domain in (None, "network"):
        from windoc.core.engine import evaluate_network_hypotheses
        with console.status("[bold green]Checking network health...[/bold green]"):
            net_results = run_all_network_checks()
        net_report = evaluate_network_hypotheses(net_results)
        reports_to_check.append((net_report, "Network"))

    if target_domain in (None, "bluetooth"):
        from windoc.core.engine import evaluate_bluetooth_hypotheses
        from windoc.domains.bluetooth import run_all_bluetooth_checks
        with console.status("[bold green]Checking Bluetooth health...[/bold green]"):
            bth_results = run_all_bluetooth_checks()
        bth_report = evaluate_bluetooth_hypotheses(bth_results)
        reports_to_check.append((bth_report, "Bluetooth"))

    if target_domain in (None, "drivers"):
        from windoc.core.engine import evaluate_driver_hypotheses
        from windoc.domains.drivers import run_all_driver_checks
        with console.status("[bold green]Checking hardware devices & drivers...[/bold green]"):
            drv_results = run_all_driver_checks()
        drv_report = evaluate_driver_hypotheses(drv_results)
        reports_to_check.append((drv_report, "Drivers"))

    if target_domain in (None, "update"):
        from windoc.core.engine import evaluate_update_hypotheses
        from windoc.domains.update import run_all_update_checks
        with console.status("[bold green]Checking Windows Update health...[/bold green]"):
            upd_results = run_all_update_checks()
        upd_report = evaluate_update_hypotheses(upd_results)
        reports_to_check.append((upd_report, "Windows Update"))

    if target_domain in (None, "system"):
        from windoc.core.engine import evaluate_system_hypotheses
        from windoc.domains.system import run_all_system_checks
        with console.status("[bold green]Checking Windows system integrity...[/bold green]"):
            sys_results = run_all_system_checks()
        sys_report = evaluate_system_hypotheses(sys_results)
        reports_to_check.append((sys_report, "System"))

    if target_domain in (None, "performance"):
        from windoc.core.engine import evaluate_performance_hypotheses
        from windoc.domains.performance import run_all_performance_checks
        with console.status("[bold green]Checking performance and storage capacity...[/bold green]"):
            perf_results = run_all_performance_checks()
        perf_report = evaluate_performance_hypotheses(perf_results)
        reports_to_check.append((perf_report, "Performance"))

    _run_auto_fixes(reports_to_check, auto_approve=yes)


def _handle_diagnose_domain(
    domain_key: str,
    domain_name: str,
    report_title: str,
    investigate_title: str,
    run_checks_fn,
    eval_fn,
    fix: bool = False,
    yes: bool = False,
) -> None:
    """Helper to diagnose a domain and optionally apply verified fixes with ease."""
    console.print(f"[bold cyan]Investigating {investigate_title}...[/bold cyan]\n")
    with console.status(f"[bold green]Executing {domain_name.lower()} checks...[/bold green]"):
        results = run_checks_fn()
    render_diagnostic_results(report_title, results)

    report = eval_fn(results)
    render_diagnosis_report(report)

    if fix:
        _run_auto_fixes([(report, domain_name)], auto_approve=yes)
    elif report.primary_finding and not report.primary_finding.cause_id.endswith("_ALL_HEALTHY"):
        repairs = registry.find_for_cause(report.primary_finding.cause_id)
        if repairs:
            is_tty = False
            try:
                is_tty = sys.stdin.isatty()
            except Exception:
                pass
            if is_tty:
                apply_now = typer.confirm(
                    f"\nWould you like WinDoc to fix '{report.primary_finding.title}' now?",
                    default=True,
                )
                if apply_now:
                    _run_auto_fixes([(report, domain_name)], auto_approve=True)
                else:
                    console.print(f"[dim]To apply later, run: [cyan]windoc fix {domain_key}[/cyan] or [cyan]windoc repair {repairs[0].repair_id}[/cyan][/dim]\n")


@diagnose_app.command(name="network")
def diagnose_network(
    fix: bool = typer.Option(False, "--fix", "-f", help="Automatically offer to apply verified fixes for detected problems"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve fixes without confirmation prompts (when using --fix)"),
) -> None:
    """Diagnose network adapters, IP configuration, gateway, DNS, and external reachability."""
    from windoc.core.engine import evaluate_network_hypotheses

    _handle_diagnose_domain("network", "Network", "Network Diagnostic Report", "Network subsystem", run_all_network_checks, evaluate_network_hypotheses, fix=fix, yes=yes)


@diagnose_app.command(name="bluetooth")
def diagnose_bluetooth(
    fix: bool = typer.Option(False, "--fix", "-f", help="Automatically offer to apply verified fixes for detected problems"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve fixes without confirmation prompts (when using --fix)"),
) -> None:
    """Diagnose Bluetooth controller hardware, services, and paired accessories."""
    from windoc.core.engine import evaluate_bluetooth_hypotheses
    from windoc.domains.bluetooth import run_all_bluetooth_checks

    _handle_diagnose_domain("bluetooth", "Bluetooth", "Bluetooth Diagnostic Report", "Bluetooth subsystem", run_all_bluetooth_checks, evaluate_bluetooth_hypotheses, fix=fix, yes=yes)


@diagnose_app.command(name="drivers")
def diagnose_drivers(
    fix: bool = typer.Option(False, "--fix", "-f", help="Automatically offer to apply verified fixes for detected problems"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve fixes without confirmation prompts (when using --fix)"),
) -> None:
    """Diagnose hardware devices, Device Manager error codes, and drivers."""
    from windoc.core.engine import evaluate_driver_hypotheses
    from windoc.domains.drivers import run_all_driver_checks

    _handle_diagnose_domain("drivers", "Drivers", "Hardware & Driver Diagnostic Report", "Hardware Devices & Drivers", run_all_driver_checks, evaluate_driver_hypotheses, fix=fix, yes=yes)


@diagnose_app.command(name="update")
def diagnose_update(
    fix: bool = typer.Option(False, "--fix", "-f", help="Automatically offer to apply verified fixes for detected problems"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve fixes without confirmation prompts (when using --fix)"),
) -> None:
    """Diagnose Windows Update services, pending reboots, and update history."""
    from windoc.core.engine import evaluate_update_hypotheses
    from windoc.domains.update import run_all_update_checks

    _handle_diagnose_domain("update", "Windows Update", "Windows Update Diagnostic Report", "Windows Update Subsystem", run_all_update_checks, evaluate_update_hypotheses, fix=fix, yes=yes)


@diagnose_app.command(name="system")
def diagnose_system(
    fix: bool = typer.Option(False, "--fix", "-f", help="Automatically offer to apply verified fixes for detected problems"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve fixes without confirmation prompts (when using --fix)"),
) -> None:
    """Diagnose Windows component store integrity, core services, and crash dumps."""
    from windoc.core.engine import evaluate_system_hypotheses
    from windoc.domains.system import run_all_system_checks

    _handle_diagnose_domain("system", "System", "Windows System Diagnostic Report", "Windows System Integrity & Core Services", run_all_system_checks, evaluate_system_hypotheses, fix=fix, yes=yes)


@diagnose_app.command(name="performance")
def diagnose_performance(
    fix: bool = typer.Option(False, "--fix", "-f", help="Automatically offer to apply verified fixes for detected problems"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve fixes without confirmation prompts (when using --fix)"),
) -> None:
    """Diagnose CPU load, physical RAM pressure, disk space, and system uptime."""
    from windoc.core.engine import evaluate_performance_hypotheses
    from windoc.domains.performance import run_all_performance_checks

    _handle_diagnose_domain("performance", "Performance", "Performance & Resource Diagnostic Report", "System Performance & Resource Capacity", run_all_performance_checks, evaluate_performance_hypotheses, fix=fix, yes=yes)


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
    repair_id: Optional[str] = typer.Argument(
        None,
        help="The identifier of the repair to execute (e.g. drv.enable_device). If omitted, automatically runs auto-fix.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip interactive confirmation prompt"),
) -> None:
    """Execute a controlled repair procedure with pre/post verification (or auto-fix if no ID is specified)."""
    if not repair_id:
        fix_cmd(yes=yes)
        return

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
    table.add_row("drivers", "Supported (Active)", "Device Manager error codes, missing drivers, disabled devices")
    table.add_row("update", "Supported (Active)", "Windows Update services, error codes, logs")
    table.add_row("system", "Supported (Active)", "System file integrity, component store, services")
    table.add_row("performance", "Supported (Active)", "CPU load, physical RAM pressure, disk space, uptime")

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
