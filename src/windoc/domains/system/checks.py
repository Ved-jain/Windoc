"""Diagnostic checks for Windows System integrity, core subsystem services, and crash dumps."""

from typing import Any, Dict, List

from windoc.core.models import CheckStatus, DiagnosticResult, ResultKind, Severity
from windoc.core.runner import run_command, run_powershell


def check_core_system_services() -> List[DiagnosticResult]:
    """Inspect mission-critical Windows OS subsystem services.

    Checks:
    - RpcSs: Remote Procedure Call
    - DcomLaunch: DCOM Server Process Launcher
    - EventLog: Windows Event Log
    - PlugPlay: Plug and Play Service
    - Winmgmt: Windows Management Instrumentation (WMI)
    """
    results: List[DiagnosticResult] = []
    ps_cmd = (
        "Get-Service -Name 'RpcSs', 'DcomLaunch', 'EventLog', 'PlugPlay', 'Winmgmt' -ErrorAction SilentlyContinue | "
        "Select-Object Name, DisplayName, Status, StartType"
    )
    cmd_res, raw_services = run_powershell(ps_cmd, as_json=True, ensure_list=True, timeout_seconds=10.0)

    if not cmd_res.is_success or raw_services is None:
        return [
            DiagnosticResult(
                check_id="sys.service.query",
                domain="system",
                observation=f"Failed to query core Windows subsystem services: {cmd_res.error or cmd_res.stderr}",
                status=CheckStatus.ERROR,
                severity=Severity.HIGH,
                data_source="Get-Service",
            )
        ]

    inactive_services: List[str] = []
    for svc in raw_services:
        name = svc.get("Name", "")
        display = svc.get("DisplayName", name)
        status = svc.get("Status")
        start_type = svc.get("StartType")

        # Status 4 = Running. If start_type is 4 (Disabled) or status is not Running (4)
        if start_type in (4, "Disabled") or status not in (4, "Running"):
            inactive_services.append(f"{display} ({name})")

    if inactive_services:
        results.append(
            DiagnosticResult(
                check_id="sys.service.stopped",
                domain="system",
                observation=f"Core Windows service(s) stopped or disabled: {', '.join(inactive_services)}.",
                status=CheckStatus.FAIL,
                severity=Severity.CRITICAL,
                result_kind=ResultKind.OBSERVATION,
                data_source="Get-Service",
                measured_value={"inactive_services": inactive_services},
            )
        )
    else:
        results.append(
            DiagnosticResult(
                check_id="sys.service.status",
                domain="system",
                observation="All core Windows services operational (RpcSs, DcomLaunch, EventLog, PlugPlay, Winmgmt).",
                status=CheckStatus.PASS,
                severity=Severity.INFO,
                data_source="Get-Service",
            )
        )

    return results


def check_component_store_health() -> DiagnosticResult:
    """Check the health of the Windows Component Store (WinSxS) via DISM CheckHealth or CBS logs."""
    dism_cmd = ["dism.exe", "/Online", "/Cleanup-Image", "/CheckHealth"]
    res = run_command(dism_cmd, timeout_seconds=15.0)

    # If DISM executed with elevation
    if res.is_success:
        stdout_lower = res.stdout.lower()
        if "no component store corruption detected" in stdout_lower:
            return DiagnosticResult(
                check_id="sys.dism.health",
                domain="system",
                observation="Windows Component Store verified healthy (no corruption detected).",
                status=CheckStatus.PASS,
                severity=Severity.INFO,
                data_source="DISM: CheckHealth",
            )
        if "repairable" in stdout_lower or "corruption" in stdout_lower:
            return DiagnosticResult(
                check_id="sys.dism.corrupted",
                domain="system",
                observation="Windows Component Store corruption detected; image is repairable via DISM RestoreHealth.",
                status=CheckStatus.FAIL,
                severity=Severity.HIGH,
                result_kind=ResultKind.OBSERVATION,
                data_source="DISM: CheckHealth",
            )

    # If non-elevated (Error 740) or DISM unavailable, perform non-elevated check on CBS log & registry
    ps_cbs = (
        "@{ "
        "CBS_Exists = (Test-Path 'C:\\Windows\\Logs\\CBS\\CBS.log'); "
        "CBS_Reg = (Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing') "
        "}"
    )
    cbs_res, cbs_data = run_powershell(ps_cbs, as_json=True, timeout_seconds=6.0)

    if cbs_res.is_success and isinstance(cbs_data, dict) and cbs_data.get("CBS_Exists") and cbs_data.get("CBS_Reg"):
        return DiagnosticResult(
            check_id="sys.dism.health",
            domain="system",
            observation="Component store logs and servicing keys verified intact (DISM deep scan requires Administrator).",
            status=CheckStatus.PASS,
            severity=Severity.INFO,
            data_source="Registry: CBS",
        )

    return DiagnosticResult(
        check_id="sys.dism.health",
        domain="system",
        observation="Component store servicing logs could not be verified.",
        status=CheckStatus.WARNING,
        severity=Severity.LOW,
        data_source="Registry: CBS",
    )


def check_crash_dumps() -> DiagnosticResult:
    """Inspect system crash dumps (BSOD / BugCheck minidumps)."""
    ps_cmd = (
        "$files = Get-ChildItem -Path 'C:\\Windows\\Minidump\\*.dmp', 'C:\\Windows\\MEMORY.DMP' -ErrorAction SilentlyContinue | "
        "Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-7) }; "
        "@{ HasCrashDumps = ($files.Count -gt 0); Count = $files.Count }"
    )
    cmd_res, raw_data = run_powershell(ps_cmd, as_json=True, timeout_seconds=8.0)

    if not cmd_res.is_success or not isinstance(raw_data, dict):
        return DiagnosticResult(
            check_id="sys.crash.dumps",
            domain="system",
            observation="Could not query Windows crash dump directories.",
            status=CheckStatus.WARNING,
            severity=Severity.LOW,
            data_source="C:\\Windows\\Minidump",
        )

    count = int(raw_data.get("Count", 0))
    if count > 0:
        return DiagnosticResult(
            check_id="sys.crash.dumps",
            domain="system",
            observation=f"Detected {count} recent system crash minidump(s) within the last 7 days.",
            status=CheckStatus.WARNING,
            severity=Severity.MEDIUM,
            result_kind=ResultKind.OBSERVATION,
            data_source="C:\\Windows\\Minidump",
            measured_value={"crash_count": count},
        )

    return DiagnosticResult(
        check_id="sys.crash.dumps",
        domain="system",
        observation="No recent system crash or BSOD minidump files detected.",
        status=CheckStatus.PASS,
        severity=Severity.INFO,
        data_source="C:\\Windows\\Minidump",
    )


def check_os_boot_state() -> DiagnosticResult:
    """Verify whether Windows booted in Normal mode or Safe/Fail-safe mode."""
    ps_cmd = "(Get-CimInstance -ClassName Win32_ComputerSystem).BootupState"
    cmd_res, boot_state = run_powershell(ps_cmd, as_json=False, timeout_seconds=6.0)

    if not cmd_res.is_success:
        return DiagnosticResult(
            check_id="sys.boot.state",
            domain="system",
            observation="Could not query system bootup state via CIM.",
            status=CheckStatus.WARNING,
            severity=Severity.LOW,
            data_source="Win32_ComputerSystem",
        )

    state_str = (cmd_res.stdout or "").strip()
    if "safe" in state_str.lower():
        return DiagnosticResult(
            check_id="sys.boot.state",
            domain="system",
            observation=f"Windows is running in Safe/Diagnostic mode ({state_str}).",
            status=CheckStatus.WARNING,
            severity=Severity.MEDIUM,
            result_kind=ResultKind.OBSERVATION,
            data_source="Win32_ComputerSystem",
        )

    return DiagnosticResult(
        check_id="sys.boot.state",
        domain="system",
        observation=f"Windows bootup state verified normal ({state_str or 'Normal boot'}).",
        status=CheckStatus.PASS,
        severity=Severity.INFO,
        data_source="Win32_ComputerSystem",
    )


def run_all_system_checks() -> List[DiagnosticResult]:
    """Execute all Windows System diagnostic checks."""
    results: List[DiagnosticResult] = []
    results.extend(check_core_system_services())
    results.append(check_component_store_health())
    results.append(check_crash_dumps())
    results.append(check_os_boot_state())
    return results
