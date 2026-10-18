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
from windoc.domains.bluetooth.checks import (
    check_bluetooth_radio_adapter,
    check_bluetooth_services,
)
from windoc.domains.drivers.checks import check_pnp_device_errors
from windoc.domains.system.checks import (
    check_component_store_health,
    check_core_system_services,
)
from windoc.domains.update.checks import check_update_services
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


def _restart_bthserv_action(**kwargs) -> CommandResult:
    """Restart Bluetooth Support Service."""
    res, _ = run_powershell("Restart-Service -Name 'bthserv' -Force", timeout_seconds=15.0)
    return res


def _restart_bthserv_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify Bluetooth Support Service is running."""
    results = check_bluetooth_services()
    is_running = any(r.check_id == "bth.service.bthserv.state" and r.status == CheckStatus.PASS for r in results)
    if is_running:
        return True, "Bluetooth Support Service is running.", results
    return False, "Bluetooth Support Service failed to start.", results


def _enable_bth_adapter_action(**kwargs) -> CommandResult:
    """Enable disabled Bluetooth adapter via PnP device management."""
    ps_cmd = (
        "Get-PnpDevice -Class Bluetooth | "
        "Where-Object { $_.ConfigManagerErrorCode -eq 22 } | "
        "Enable-PnpDevice -Confirm:$false"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=15.0)
    return res


def _enable_bth_adapter_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify Bluetooth adapter is operational after enabling."""
    results = check_bluetooth_radio_adapter()
    is_ok = any(r.check_id == "bth.adapter.operational" and r.status == CheckStatus.PASS for r in results)
    if is_ok:
        return True, "Bluetooth controller successfully enabled and operational.", results
    return False, "Bluetooth controller remains disabled or reported errors.", results


def _rescan_devices_action(**kwargs) -> CommandResult:
    """Rescan PnP hardware device tree via pnputil."""
    res = run_command(["pnputil.exe", "/scan-devices"], timeout_seconds=20.0)
    return res


def _rescan_devices_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify whether PnP devices in error have recovered after rescan."""
    results = check_pnp_device_errors()
    faults = [r for r in results if r.check_id in ("drv.device.code_43", "drv.device.code_10")]
    if not faults:
        return True, "Hardware rescan completed. No active device errors detected.", results
    return False, f"Hardware rescan completed, but {len(faults)} device(s) remain in error state.", results


def _enable_devices_action(**kwargs) -> CommandResult:
    """Re-enable any disabled PnP devices."""
    ps_cmd = (
        "Get-PnpDevice | "
        "Where-Object { $_.ConfigManagerErrorCode -eq 22 } | "
        "Enable-PnpDevice -Confirm:$false"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=20.0)
    return res


def _enable_devices_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify disabled devices have been re-enabled."""
    results = check_pnp_device_errors()
    disabled = [r for r in results if r.check_id == "drv.device.code_22"]
    if not disabled:
        return True, "All previously disabled hardware devices successfully enabled.", results
    return False, f"{len(disabled)} device(s) remain disabled.", results


def _reset_update_services_action(**kwargs) -> CommandResult:
    """Re-enable and start core Windows Update background services."""
    ps_cmd = (
        "Set-Service -Name 'wuauserv' -StartupType Automatic -ErrorAction SilentlyContinue; "
        "Set-Service -Name 'bits' -StartupType Manual -ErrorAction SilentlyContinue; "
        "Set-Service -Name 'cryptsvc' -StartupType Automatic -ErrorAction SilentlyContinue; "
        "Start-Service -Name 'wuauserv', 'cryptsvc' -ErrorAction SilentlyContinue"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=20.0)
    return res


def _reset_update_services_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify Windows Update services are no longer disabled."""
    results = check_update_services()
    disabled = [r for r in results if r.check_id == "upd.service.disabled"]
    if not disabled:
        return True, "Windows Update background services re-enabled and restored.", results
    return False, f"Failed to restore all update services: {disabled[0].observation}", results


def _repair_component_store_action(**kwargs) -> CommandResult:
    """Repair corrupted Windows component store using DISM RestoreHealth."""
    cmd = ["dism.exe", "/Online", "/Cleanup-Image", "/RestoreHealth"]
    return run_command(cmd, timeout_seconds=180.0)


def _repair_component_store_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify Windows Component Store after RestoreHealth repair."""
    res = check_component_store_health()
    if res.status == CheckStatus.PASS:
        return True, "Windows Component Store successfully restored to healthy state.", [res]
    return False, f"Component store issue persists: {res.observation}", [res]


def _restart_system_services_action(**kwargs) -> CommandResult:
    """Ensure essential Windows OS subsystem services are configured and running."""
    ps_cmd = (
        "Set-Service -Name 'RpcSs' -StartupType Automatic -ErrorAction SilentlyContinue; "
        "Set-Service -Name 'DcomLaunch' -StartupType Automatic -ErrorAction SilentlyContinue; "
        "Set-Service -Name 'EventLog' -StartupType Automatic -ErrorAction SilentlyContinue; "
        "Set-Service -Name 'Winmgmt' -StartupType Automatic -ErrorAction SilentlyContinue; "
        "Start-Service -Name 'EventLog', 'Winmgmt' -ErrorAction SilentlyContinue"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=20.0)
    return res


def _restart_system_services_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify core Windows subsystem services are running."""
    results = check_core_system_services()
    stopped = [r for r in results if r.check_id == "sys.service.stopped"]
    if not stopped:
        return True, "All core Windows subsystem services are active and running.", results
    return False, f"Core service(s) failed to start: {stopped[0].observation}", results


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

        self.register(
            RepairAction(
                repair_id="bth.restart_service",
                name="Restart Bluetooth Support Service",
                description="Restarts the Windows Bluetooth Support Service (bthserv) to recover stalled Bluetooth communications.",
                target_cause_id="BTH_SERVICE_STOPPED",
                risk_level=RiskLevel.LOW,
                requires_admin=True,
                expected_effects="Briefly reloads Bluetooth subsystem services.",
                timeout_seconds=15.0,
                action_fn=_restart_bthserv_action,
                verify_fn=_restart_bthserv_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="bth.enable_adapter",
                name="Enable Bluetooth Controller",
                description="Re-enables an administratively disabled Bluetooth radio adapter via Windows PnP Device Manager.",
                target_cause_id="BTH_ADAPTER_DISABLED",
                risk_level=RiskLevel.LOW,
                requires_admin=True,
                expected_effects="Enables Bluetooth radio and restores device discovery / pairing.",
                timeout_seconds=15.0,
                action_fn=_enable_bth_adapter_action,
                verify_fn=_enable_bth_adapter_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="drv.rescan_devices",
                name="Rescan Hardware Devices",
                description="Triggers Windows Plug and Play to re-enumerate the device tree and reload unresponsive hardware using pnputil.",
                target_cause_id="DRV_DEVICE_CRASHED_CODE_43",
                risk_level=RiskLevel.LOW,
                requires_admin=True,
                expected_effects="Windows refreshes hardware device states and attempts to reload stalled drivers.",
                timeout_seconds=20.0,
                action_fn=_rescan_devices_action,
                verify_fn=_rescan_devices_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="drv.enable_device",
                name="Re-enable Disabled Hardware Devices",
                description="Re-enables any connected PnP devices currently disabled in Windows Device Manager.",
                target_cause_id="DRV_DEVICE_DISABLED_CODE_22",
                risk_level=RiskLevel.LOW,
                requires_admin=True,
                expected_effects="Re-enables disabled hardware components and starts device drivers.",
                timeout_seconds=20.0,
                action_fn=_enable_devices_action,
                verify_fn=_enable_devices_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="upd.reset_services",
                name="Reset and Enable Windows Update Services",
                description="Restores startup configuration and starts wuauserv, bits, and cryptsvc background services.",
                target_cause_id="UPD_SERVICES_DISABLED",
                risk_level=RiskLevel.LOW,
                requires_admin=True,
                expected_effects="Enables Windows Update and cryptographic services to resume downloading updates.",
                timeout_seconds=20.0,
                action_fn=_reset_update_services_action,
                verify_fn=_reset_update_services_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="sys.repair_component_store",
                name="Repair Component Store (DISM RestoreHealth)",
                description="Repairs corrupted Windows system packages using DISM RestoreHealth against Windows Update component store.",
                target_cause_id="SYS_COMPONENT_STORE_CORRUPT",
                risk_level=RiskLevel.MEDIUM,
                requires_admin=True,
                expected_effects="Replaces corrupted or missing system files in the Windows Component Store (WinSxS).",
                timeout_seconds=180.0,
                action_fn=_repair_component_store_action,
                verify_fn=_repair_component_store_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="sys.restart_services",
                name="Restore Essential System Services",
                description="Re-enables and starts essential Windows OS subsystem services including WMI and EventLog.",
                target_cause_id="SYS_CORE_SERVICES_STOPPED",
                risk_level=RiskLevel.LOW,
                requires_admin=True,
                expected_effects="Restores core Windows subsystem services to Automatic startup and active state.",
                timeout_seconds=20.0,
                action_fn=_restart_system_services_action,
                verify_fn=_restart_system_services_verify,
            )
        )


registry = RepairRegistry()
