"""Windows System integrity, core services, and crash diagnostics domain."""

from windoc.domains.system.checks import (
    check_component_store_health,
    check_core_system_services,
    check_crash_dumps,
    check_os_boot_state,
    run_all_system_checks,
)

__all__ = [
    "check_component_store_health",
    "check_core_system_services",
    "check_crash_dumps",
    "check_os_boot_state",
    "run_all_system_checks",
]
