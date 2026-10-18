"""Approved registry of controlled, allowlisted repair procedures."""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from windoc.core.models import CheckStatus, DiagnosticResult
from windoc.core.runner import CommandResult, run_command, run_powershell
from windoc.domains.network.checks import (
    check_dns_resolution,
    check_ip_configuration,
    check_network_adapters,
)
from windoc.repairs.models import RiskLevel


@dataclass
class RepairAction:
    """Predefined, allowlisted repair specification."""
    repair_id: str
    name: str
    description: str
    target_cause_id: str
    risk_level: RiskLevel
    requires_admin: bool
    expected_effects: str
    timeout_seconds: float
    action_fn: Callable[..., CommandResult]
    verify_fn: Callable[..., Tuple[bool, str, List[DiagnosticResult]]]
    requires_restart: bool = False
    pre_state_fn: Optional[Callable[..., Dict]] = None


# --- Repair Actions Implementation ---

def _flush_dns_action(**kwargs) -> CommandResult:
    """Execute ipconfig /flushdns."""
    return run_command(["ipconfig.exe", "/flushdns"], timeout_seconds=10.0)


def _flush_dns_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify DNS resolution after cache flush."""
    results = check_dns_resolution()
    resolved = any(r.check_id == "net.dns.resolution" and r.status in (CheckStatus.PASS, CheckStatus.WARNING) for r in results)
    if resolved:
        return True, "DNS resolution verified successfully after cache flush.", results
    return False, "DNS resolution continues to fail after cache flush.", results


def _renew_dhcp_action(**kwargs) -> CommandResult:
    """Execute ipconfig /renew."""
    return run_command(["ipconfig.exe", "/renew"], timeout_seconds=20.0)


def _renew_dhcp_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify IP configuration after DHCP renew."""
    results = check_ip_configuration()
    has_valid = any(r.check_id == "net.ip.status" and r.status == CheckStatus.PASS for r in results)
    if has_valid:
        return True, "Valid IPv4 address obtained via DHCP.", results
    return False, "DHCP renew did not resolve APIPA or missing IP address.", results


def _restart_adapter_action(adapter_name: str = "Wi-Fi", **kwargs) -> CommandResult:
    """Restart network adapter using Restart-NetAdapter cmdlet."""
    ps_cmd = f"Restart-NetAdapter -Name '{adapter_name}' -Confirm:$false"
    res, _ = run_powershell(ps_cmd, timeout_seconds=20.0)
    return res


def _restart_adapter_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify adapter state after restart."""
    results = check_network_adapters()
    is_up = any(r.status == CheckStatus.PASS for r in results if r.check_id.startswith("net.adapter."))
    if is_up:
        return True, "Network adapter successfully re-initialized and is operational.", results
    return False, "Network adapter remains disconnected or disabled.", results


class RepairRegistry:
    """Central repository of authorized repair operations."""

    def __init__(self) -> None:
        self._repairs: Dict[str, RepairAction] = {}
        self._register_defaults()

    def register(self, action: RepairAction) -> None:
        """Register a new allowlisted repair action."""
        self._repairs[action.repair_id] = action

    def get(self, repair_id: str) -> Optional[RepairAction]:
        """Retrieve a repair action by its unique identifier."""
        return self._repairs.get(repair_id)

    def find_for_cause(self, cause_id: str) -> List[RepairAction]:
        """Find all approved repair actions matching a diagnosed root cause."""
        return [r for r in self._repairs.values() if r.target_cause_id == cause_id]

    def list_all(self) -> List[RepairAction]:
        """Return all registered repair actions."""
        return list(self._repairs.values())

    def _register_defaults(self) -> None:
        """Register default approved repair operations for Version 1."""
        self.register(
            RepairAction(
                repair_id="net.flush_dns",
                name="Flush DNS Resolver Cache",
                description="Flushes and resets the contents of the Windows DNS client cache to clear stale or corrupt entries.",
                target_cause_id="NET_DNS_RESOLUTION_FAILED",
                risk_level=RiskLevel.LOW,
                requires_admin=False,
                expected_effects="Clears DNS cache; next DNS query will fetch directly from configured upstream servers.",
                timeout_seconds=10.0,
                action_fn=_flush_dns_action,
                verify_fn=_flush_dns_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="net.renew_dhcp",
                name="Renew DHCP IP Lease",
                description="Releases the current IP address and requests a fresh lease from the local DHCP router.",
                target_cause_id="NET_DHCP_LEASE_FAILED",
                risk_level=RiskLevel.LOW,
                requires_admin=False,
                expected_effects="Brief network pause while router re-assigns an IPv4 address.",
                timeout_seconds=25.0,
                action_fn=_renew_dhcp_action,
                verify_fn=_renew_dhcp_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="net.restart_adapter",
                name="Restart Network Adapter",
                description="Power cycles the network adapter by disabling and re-enabling it via Windows Network Management.",
                target_cause_id="NET_PHYSICAL_DISCONNECTED",
                risk_level=RiskLevel.MEDIUM,
                requires_admin=True,
                expected_effects="Temporarily drops network connections on the adapter for 3-5 seconds.",
                timeout_seconds=20.0,
                action_fn=_restart_adapter_action,
                verify_fn=_restart_adapter_verify,
            )
        )


registry = RepairRegistry()
