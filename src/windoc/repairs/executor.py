"""Controlled repair execution engine enforcing authorization, permissions, and verification."""

import ctypes
from typing import Any, Callable, Dict, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from windoc.repairs.models import RepairExecutionResult, RepairStatus, RiskLevel
from windoc.repairs.registry import RepairAction

console = Console()


def check_is_admin() -> bool:
    """Return True if current process has Administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except (AttributeError, OSError):
        return False


def execute_repair(
    repair: RepairAction,
    auto_approve: bool = False,
    prompt_fn: Optional[Callable[[str], bool]] = None,
    **kwargs: Any,
) -> RepairExecutionResult:
    """Safely execute an authorized repair operation with strict pre- and post-conditions.
    
    Interview Defense:
    1. Checks administrative privileges BEFORE touching system state.
    2. Enforces explicit user consent (unless non-interactive flag is passed).
    3. Executes allowlisted command with hard timeout.
    4. Re-runs independent diagnostic checks to verify resolution.
    5. Flags 'VERIFICATION_FAILED' if exit code was 0 but the problem persists!
    """
    # 1. Permission check
    if repair.requires_admin and not check_is_admin():
        return RepairExecutionResult(
            repair_id=repair.repair_id,
            name=repair.name,
            status=RepairStatus.PERMISSION_DENIED,
            message=(
                f"Repair '{repair.name}' requires Administrator privileges.\n"
                "Please re-run this command from an elevated PowerShell / Command Prompt terminal (Run as Administrator)."
            ),
        )

    # 2. User authorization / consent check
    if not auto_approve:
        if prompt_fn:
            authorized = prompt_fn(f"Authorize execution of '{repair.name}'?")
        else:
            console.print(
                Panel(
                    f"[bold yellow]Proposed Repair:[/bold yellow] [bold white]{repair.name}[/bold white]\n"
                    f"[dim]ID: {repair.repair_id}[/dim]\n\n"
                    f"[white]{repair.description}[/white]\n\n"
                    f"[bold cyan]Risk Level:[/bold cyan] {repair.risk_level.value}\n"
                    f"[bold cyan]Expected Effects:[/bold cyan] {repair.expected_effects}\n"
                    f"[bold cyan]Requires Admin:[/bold cyan] {'Yes' if repair.requires_admin else 'No'}",
                    title="[bold yellow]Repair Authorization Request[/bold yellow]",
                    border_style="yellow",
                )
            )
            authorized = Confirm.ask(
                "[bold cyan]Do you authorize WinDoc to execute this repair?[/bold cyan]",
                default=False,
            )

        if not authorized:
            return RepairExecutionResult(
                repair_id=repair.repair_id,
                name=repair.name,
                status=RepairStatus.ABORTED,
                message=f"Repair '{repair.name}' was cancelled by user.",
            )

    # 3. Capture Pre-repair state
    pre_state: Dict[str, Any] = {}
    if repair.pre_state_fn:
        try:
            pre_state = repair.pre_state_fn(**kwargs)
        except Exception:
            pre_state = {}

    # 4. Execute the allowlisted repair command
    try:
        cmd_result = repair.action_fn(**kwargs)
        if isinstance(cmd_result, tuple):
            cmd_result = cmd_result[0]
    except Exception as exc:
        return RepairExecutionResult(
            repair_id=repair.repair_id,
            name=repair.name,
            status=RepairStatus.FAILED,
            message=f"Execution error while launching repair: {exc}",
            pre_state=pre_state,
        )

    if not cmd_result.is_success:
        return RepairExecutionResult(
            repair_id=repair.repair_id,
            name=repair.name,
            status=RepairStatus.FAILED,
            message=f"Repair command exited with code {cmd_result.exit_code}: {cmd_result.error or cmd_result.stderr}",
            command_result=cmd_result,
            pre_state=pre_state,
        )

    # 5. Post-repair independent verification
    try:
        verified, verif_msg, verif_results = repair.verify_fn(**kwargs)
    except Exception as exc:
        return RepairExecutionResult(
            repair_id=repair.repair_id,
            name=repair.name,
            status=RepairStatus.PARTIAL_SUCCESS,
            message=f"Command executed, but verification raised an error: {exc}",
            command_result=cmd_result,
            pre_state=pre_state,
            verified=False,
        )

    if verified:
        return RepairExecutionResult(
            repair_id=repair.repair_id,
            name=repair.name,
            status=RepairStatus.SUCCESS,
            message=f"Repair succeeded: {verif_msg}",
            command_result=cmd_result,
            pre_state=pre_state,
            verified=True,
            verification_results=verif_results,
        )
    else:
        return RepairExecutionResult(
            repair_id=repair.repair_id,
            name=repair.name,
            status=RepairStatus.VERIFICATION_FAILED,
            message=(
                f"Command completed successfully (exit code 0), but independent verification failed.\n"
                f"Details: {verif_msg}"
            ),
            command_result=cmd_result,
            pre_state=pre_state,
            verified=False,
            verification_results=verif_results,
        )
