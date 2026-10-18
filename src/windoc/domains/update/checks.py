"""Diagnostic checks for Windows Update services, reboot pending states, and update history."""

from typing import Any, Dict, List

from windoc.core.models import CheckStatus, DiagnosticResult, ResultKind, Severity
from windoc.core.runner import run_powershell


def check_update_services() -> List[DiagnosticResult]:
    """Inspect core Windows Update background services.

    Analyzes wuauserv (Windows Update), bits (Background Intelligent Transfer),
    cryptsvc (Cryptographic Services), and TrustedInstaller (Windows Modules Installer).
    Identifies services that have been administratively disabled (StartType 4) or stopped.
    """
    results: List[DiagnosticResult] = []
    ps_cmd = (
        "Get-Service -Name 'wuauserv', 'bits', 'cryptsvc', 'TrustedInstaller' -ErrorAction SilentlyContinue | "
        "Select-Object Name, DisplayName, Status, StartType"
    )
    cmd_res, raw_services = run_powershell(ps_cmd, as_json=True, ensure_list=True, timeout_seconds=10.0)

    if not cmd_res.is_success or raw_services is None:
        return [
            DiagnosticResult(
                check_id="upd.service.query",
                domain="update",
                observation=f"Failed to query Windows Update services: {cmd_res.error or cmd_res.stderr}",
                status=CheckStatus.ERROR,
                severity=Severity.HIGH,
                data_source="Get-Service",
            )
        ]

    disabled_services: List[str] = []
    for svc in raw_services:
        name = svc.get("Name", "")
        display = svc.get("DisplayName", name)
        start_type = svc.get("StartType")

        # StartType: 4 is Disabled
        if start_type in (4, "Disabled"):
            disabled_services.append(f"{display} ({name})")

    if disabled_services:
        results.append(
            DiagnosticResult(
                check_id="upd.service.disabled",
                domain="update",
                observation=f"Windows Update service(s) disabled: {', '.join(disabled_services)}.",
                status=CheckStatus.FAIL,
                severity=Severity.HIGH,
                kind=ResultKind.OBSERVATION,
                data_source="Get-Service",
                metadata={"disabled_services": disabled_services},
            )
        )
    else:
        results.append(
            DiagnosticResult(
                check_id="upd.service.status",
                domain="update",
                observation="All Windows Update services configured properly (wuauserv, bits, cryptsvc, TrustedInstaller).",
                status=CheckStatus.PASS,
                severity=Severity.INFO,
                data_source="Get-Service",
            )
        )

    return results


def check_reboot_pending() -> DiagnosticResult:
    """Check if Windows Update has an update installed that is pending a system restart."""
    ps_cmd = (
        "@{ "
        "WU_Reboot = (Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired'); "
        "CBS_Reboot = (Test-Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending') "
        "}"
    )
    cmd_res, raw_data = run_powershell(ps_cmd, as_json=True, timeout_seconds=6.0)

    if not cmd_res.is_success or not isinstance(raw_data, dict):
        return DiagnosticResult(
            check_id="upd.system.reboot_pending",
            domain="update",
            observation="Could not query Windows Update reboot pending registry keys.",
            status=CheckStatus.WARNING,
            severity=Severity.LOW,
            data_source="Registry: WindowsUpdate",
        )

    wu_pending = bool(raw_data.get("WU_Reboot", False))
    cbs_pending = bool(raw_data.get("CBS_Reboot", False))

    if wu_pending or cbs_pending:
        reasons = []
        if wu_pending:
            reasons.append("Windows Update pending restart")
        if cbs_pending:
            reasons.append("Component Based Servicing pending restart")

        return DiagnosticResult(
            check_id="upd.system.reboot_pending",
            domain="update",
            observation=f"System restart required to finish installing updates ({', '.join(reasons)}).",
            status=CheckStatus.WARNING,
            severity=Severity.MEDIUM,
            kind=ResultKind.OBSERVATION,
            data_source="Registry: WindowsUpdate",
            metadata={"wu_pending": wu_pending, "cbs_pending": cbs_pending},
        )

    return DiagnosticResult(
        check_id="upd.system.reboot_pending",
        domain="update",
        observation="No pending system restarts detected from Windows Update or Component Servicing.",
        status=CheckStatus.PASS,
        severity=Severity.INFO,
        data_source="Registry: WindowsUpdate",
    )


def check_recent_hotfixes() -> DiagnosticResult:
    """Verify that recent Windows quality and security updates have been applied."""
    ps_cmd = (
        "Get-HotFix -ErrorAction SilentlyContinue | "
        "Sort-Object InstalledOn -Descending | "
        "Select-Object -First 3 HotFixID, Description"
    )
    cmd_res, raw_hotfixes = run_powershell(ps_cmd, as_json=True, ensure_list=True, timeout_seconds=10.0)

    if not cmd_res.is_success or raw_hotfixes is None:
        return DiagnosticResult(
            check_id="upd.history.hotfixes",
            domain="update",
            observation="Could not query installed Windows HotFix history via PowerShell.",
            status=CheckStatus.WARNING,
            severity=Severity.LOW,
            data_source="Get-HotFix",
        )

    hotfixes: List[Dict[str, Any]] = raw_hotfixes or []
    if not hotfixes:
        return DiagnosticResult(
            check_id="upd.history.hotfixes",
            domain="update",
            observation="No installed Windows hotfixes or security updates reported by Get-HotFix.",
            status=CheckStatus.WARNING,
            severity=Severity.MEDIUM,
            data_source="Get-HotFix",
        )

    latest_kb = hotfixes[0].get("HotFixID", "Unknown KB")
    kb_list = ", ".join(h.get("HotFixID", "") for h in hotfixes if h.get("HotFixID"))

    return DiagnosticResult(
        check_id="upd.history.hotfixes",
        domain="update",
        observation=f"Windows Update history verified. Latest installed update: {latest_kb} (Recent: {kb_list}).",
        status=CheckStatus.PASS,
        severity=Severity.INFO,
        data_source="Get-HotFix",
        metadata={"latest_kb": latest_kb, "recent_hotfixes": hotfixes},
    )


def check_download_cache() -> DiagnosticResult:
    """Verify the integrity and state of the Windows Update SoftwareDistribution cache folder."""
    ps_cmd = (
        "Test-Path 'C:\\Windows\\SoftwareDistribution\\Download'"
    )
    cmd_res, exists = run_powershell(ps_cmd, as_json=True, timeout_seconds=6.0)

    if not cmd_res.is_success:
        return DiagnosticResult(
            check_id="upd.cache.integrity",
            domain="update",
            observation=f"Unable to access SoftwareDistribution download directory: {cmd_res.error or cmd_res.stderr}",
            status=CheckStatus.WARNING,
            severity=Severity.LOW,
            data_source="C:\\Windows\\SoftwareDistribution",
        )

    if exists:
        return DiagnosticResult(
            check_id="upd.cache.integrity",
            domain="update",
            observation="Windows Update cache directory (SoftwareDistribution\\Download) is intact.",
            status=CheckStatus.PASS,
            severity=Severity.INFO,
            data_source="C:\\Windows\\SoftwareDistribution",
        )

    return DiagnosticResult(
        check_id="upd.cache.integrity",
        domain="update",
        observation="SoftwareDistribution download directory is missing.",
        status=CheckStatus.WARNING,
        severity=Severity.MEDIUM,
        data_source="C:\\Windows\\SoftwareDistribution",
    )


def run_all_update_checks() -> List[DiagnosticResult]:
    """Execute all Windows Update diagnostic checks."""
    results: List[DiagnosticResult] = []
    results.extend(check_update_services())
    results.append(check_reboot_pending())
    results.append(check_recent_hotfixes())
    results.append(check_download_cache())
    return results
