"""Network diagnostics domain for WinDoc."""

from windoc.domains.network.checks import (
    check_default_gateway,
    check_dns_resolution,
    check_internet_connectivity,
    check_ip_configuration,
    check_network_adapters,
    check_proxy_and_vpn,
    run_all_network_checks,
)

__all__ = [
    "check_default_gateway",
    "check_dns_resolution",
    "check_internet_connectivity",
    "check_ip_configuration",
    "check_network_adapters",
    "check_proxy_and_vpn",
    "run_all_network_checks",
]
