"""Diagnostic checks for Windows Performance, CPU load, RAM pressure, disk space, and uptime."""

from typing import List

from windoc.core.models import CheckStatus, DiagnosticResult, ResultKind, Severity
from windoc.core.runner import run_powershell


def check_cpu_utilization() -> DiagnosticResult:
    """Measure processor utilization across CPU cores."""
    ps_cmd = "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"
    cmd_res, raw_load = run_powershell(ps_cmd, as_json=False, timeout_seconds=6.0)

    if not cmd_res.is_success:
        return DiagnosticResult(
            check_id="perf.cpu.utilization",
            domain="performance",
            observation="Could not query CPU utilization via CIM.",
            status=CheckStatus.WARNING,
            severity=Severity.LOW,
            data_source="Win32_Processor",
        )

    try:
        cpu_load = float(cmd_res.stdout.strip())
    except (ValueError, TypeError):
        cpu_load = 0.0

    if cpu_load >= 90.0:
        return DiagnosticResult(
            check_id="perf.cpu.utilization",
            domain="performance",
            observation=f"High CPU utilization detected: {int(cpu_load)}% sustained load.",
            status=CheckStatus.WARNING,
            severity=Severity.HIGH,
            kind=ResultKind.OBSERVATION,
            data_source="Win32_Processor",
            metadata={"cpu_percentage": cpu_load},
        )

    return DiagnosticResult(
        check_id="perf.cpu.utilization",
        domain="performance",
        observation=f"CPU load is within normal operating limits ({int(cpu_load)}%).",
        status=CheckStatus.PASS,
        severity=Severity.INFO,
        data_source="Win32_Processor",
        metadata={"cpu_percentage": cpu_load},
    )


def check_memory_pressure() -> DiagnosticResult:
    """Measure physical RAM consumption and memory pressure."""
    ps_cmd = (
        "$os = Get-CimInstance Win32_OperatingSystem; "
        "@{ TotalKB = $os.TotalVisibleMemorySize; FreeKB = $os.FreePhysicalMemory }"
    )
    cmd_res, raw_data = run_powershell(ps_cmd, as_json=True, timeout_seconds=6.0)

    if not cmd_res.is_success or not isinstance(raw_data, dict):
        return DiagnosticResult(
            check_id="perf.memory.pressure",
            domain="performance",
            observation="Could not query physical memory status.",
            status=CheckStatus.WARNING,
            severity=Severity.LOW,
            data_source="Win32_OperatingSystem",
        )

    total_kb = float(raw_data.get("TotalKB", 1))
    free_kb = float(raw_data.get("FreeKB", 0))
    used_pct = round(((total_kb - free_kb) / total_kb) * 100.0, 1)
    total_gb = round(total_kb / (1024 * 1024), 1)
    free_gb = round(free_kb / (1024 * 1024), 1)

    if used_pct >= 92.0:
        return DiagnosticResult(
            check_id="perf.memory.pressure",
            domain="performance",
            observation=f"Severe memory exhaustion: {used_pct}% RAM used (only {free_gb} GB free of {total_gb} GB).",
            status=CheckStatus.WARNING,
            severity=Severity.HIGH,
            kind=ResultKind.OBSERVATION,
            data_source="Win32_OperatingSystem",
            metadata={"used_percent": used_pct, "free_gb": free_gb, "total_gb": total_gb},
        )

    return DiagnosticResult(
        check_id="perf.memory.pressure",
        domain="performance",
        observation=f"Physical RAM capacity is healthy: {used_pct}% used ({free_gb} GB available of {total_gb} GB).",
        status=CheckStatus.PASS,
        severity=Severity.INFO,
        data_source="Win32_OperatingSystem",
        metadata={"used_percent": used_pct, "free_gb": free_gb, "total_gb": total_gb},
    )


def check_disk_space() -> DiagnosticResult:
    """Verify available storage space on Windows system drive (C:)."""
    ps_cmd = (
        "$v = Get-Volume -DriveLetter C -ErrorAction SilentlyContinue; "
        "@{ TotalBytes = $v.Size; FreeBytes = $v.SizeRemaining }"
    )
    cmd_res, raw_data = run_powershell(ps_cmd, as_json=True, timeout_seconds=6.0)

    if not cmd_res.is_success or not isinstance(raw_data, dict):
        return DiagnosticResult(
            check_id="perf.disk.space",
            domain="performance",
            observation="Could not query system drive C: storage capacity.",
            status=CheckStatus.WARNING,
            severity=Severity.LOW,
            data_source="Get-Volume C:",
        )

    total_bytes = float(raw_data.get("TotalBytes", 1))
    free_bytes = float(raw_data.get("FreeBytes", 0))
    free_gb = round(free_bytes / (1024**3), 1)
    total_gb = round(total_bytes / (1024**3), 1)
    free_pct = round((free_bytes / total_bytes) * 100.0, 1)

    if free_gb < 10.0 or free_pct < 10.0:
        return DiagnosticResult(
            check_id="perf.disk.space",
            domain="performance",
            observation=f"Low disk space on system drive C:: {free_gb} GB free ({free_pct}% remaining of {total_gb} GB).",
            status=CheckStatus.WARNING,
            severity=Severity.HIGH,
            kind=ResultKind.OBSERVATION,
            data_source="Get-Volume C:",
            metadata={"free_gb": free_gb, "free_percent": free_pct, "total_gb": total_gb},
        )

    return DiagnosticResult(
        check_id="perf.disk.space",
        domain="performance",
        observation=f"System drive C: storage is healthy: {free_gb} GB available ({free_pct}% free of {total_gb} GB).",
        status=CheckStatus.PASS,
        severity=Severity.INFO,
        data_source="Get-Volume C:",
        metadata={"free_gb": free_gb, "free_percent": free_pct, "total_gb": total_gb},
    )


def check_system_uptime() -> DiagnosticResult:
    """Measure continuous Windows system operating uptime."""
    ps_cmd = "[math]::Round(((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalHours, 1)"
    cmd_res, raw_hours = run_powershell(ps_cmd, as_json=False, timeout_seconds=6.0)

    if not cmd_res.is_success:
        return DiagnosticResult(
            check_id="perf.system.uptime",
            domain="performance",
            observation="Could not query system boot uptime.",
            status=CheckStatus.WARNING,
            severity=Severity.LOW,
            data_source="Win32_OperatingSystem",
        )

    try:
        hours = float(cmd_res.stdout.strip())
    except (ValueError, TypeError):
        hours = 0.0

    days = round(hours / 24.0, 1)

    if days > 30.0:
        return DiagnosticResult(
            check_id="perf.system.uptime",
            domain="performance",
            observation=f"Extended system uptime: {days} days without a reboot. A restart is recommended to clear accumulated kernel and driver leaks.",
            status=CheckStatus.WARNING,
            severity=Severity.MEDIUM,
            kind=ResultKind.OBSERVATION,
            data_source="Win32_OperatingSystem",
            metadata={"uptime_days": days, "uptime_hours": hours},
        )

    return DiagnosticResult(
        check_id="perf.system.uptime",
        domain="performance",
        observation=f"System uptime is normal: {days} days ({hours} hours since last boot).",
        status=CheckStatus.PASS,
        severity=Severity.INFO,
        data_source="Win32_OperatingSystem",
        metadata={"uptime_days": days, "uptime_hours": hours},
    )


def run_all_performance_checks() -> List[DiagnosticResult]:
    """Execute all performance and resource utilization checks."""
    results: List[DiagnosticResult] = []
    results.append(check_cpu_utilization())
    results.append(check_memory_pressure())
    results.append(check_disk_space())
    results.append(check_system_uptime())
    return results
