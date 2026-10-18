"""Windows Performance and resource diagnostics domain (CPU, RAM, Disk, Uptime)."""

from windoc.domains.performance.checks import (
    check_cpu_utilization,
    check_disk_space,
    check_memory_pressure,
    check_system_uptime,
    run_all_performance_checks,
)

__all__ = [
    "check_cpu_utilization",
    "check_disk_space",
    "check_memory_pressure",
    "check_system_uptime",
    "run_all_performance_checks",
]
