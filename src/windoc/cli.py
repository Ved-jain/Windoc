"""Command-line interface for WinDoc."""

import platform
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from windoc import __version__

app = typer.Typer(
    name="windoc",
    help="Evidence-driven Windows diagnostics and repair CLI.",
    add_completion=False,
    no_args_is_help=True,
)
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


@app.command()
def list_domains() -> None:
    """List diagnostic domains supported or planned by WinDoc."""
    table = Table(title="Diagnostic Domains", border_style="cyan")
    table.add_column("Domain", style="bold yellow")
    table.add_column("Status", style="green")
    table.add_column("Description", style="white")

    table.add_row("network", "Planned (Milestone 3)", "Wi-Fi, Ethernet, IP config, Gateway, DNS")
    table.add_row("bluetooth", "Planned (Milestone 6)", "Adapter state, service, device connection")
    table.add_row("drivers", "Planned (Milestone 7)", "Device Manager error codes, missing devices")
    table.add_row("update", "Planned (Milestone 8)", "Windows Update services, error codes, logs")
    table.add_row("system", "Planned (Milestone 9)", "System file integrity, component store, services")
    table.add_row("performance", "Planned (Milestone 10)", "CPU, RAM, disk utilization, resource spikes")

    console.print(table)


if __name__ == "__main__":
    app()
