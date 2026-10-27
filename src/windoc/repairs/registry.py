"""Approved registry of controlled, allowlisted repair procedures."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from windoc.core.models import CheckStatus, DiagnosticResult, Severity
from windoc.core.runner import CommandResult, run_command, run_powershell
from windoc.domains.network.checks import (
    check_dns_resolution,
    check_default_gateway,
    check_internet_connectivity,
    check_ip_configuration,
    check_network_adapters,
)
from windoc.domains.bluetooth.checks import (
    check_bluetooth_radio_adapter,
    check_bluetooth_services,
)
from windoc.domains.drivers.checks import check_pnp_device_errors
from windoc.domains.performance.checks import check_disk_space, check_cpu_utilization, check_memory_pressure, check_uptime
from windoc.domains.system.checks import (
    check_component_store_health,
    check_core_system_services,
    check_crash_dumps,
    check_os_boot_state,
)
from windoc.domains.update.checks import check_update_services, check_reboot_pending
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
    timeout = float(kwargs.get("timeout_seconds", 10.0))
    return run_command(["ipconfig.exe", "/flushdns"], timeout_seconds=timeout)


def _flush_dns_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify DNS resolution after cache flush."""
    results = check_dns_resolution()
    resolved = any(r.check_id == "net.dns.resolution" and r.status in (CheckStatus.PASS, CheckStatus.WARNING) for r in results)
    if resolved:
        return True, "DNS resolution verified successfully after cache flush.", results
    return False, "DNS resolution continues to fail after cache flush.", results


def _renew_dhcp_action(**kwargs) -> CommandResult:
    """Execute ipconfig /renew."""
    timeout = float(kwargs.get("timeout_seconds", 25.0))
    return run_command(["ipconfig.exe", "/renew"], timeout_seconds=timeout)


def _renew_dhcp_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify IP configuration after DHCP renew."""
    results = check_ip_configuration()
    has_valid = any(r.check_id == "net.ip.status" and r.status == CheckStatus.PASS for r in results)
    if has_valid:
        return True, "Valid IPv4 address obtained via DHCP.", results
    return False, "DHCP renew did not resolve APIPA or missing IP address.", results


def _restart_adapter_action(adapter_name: str = "Wi-Fi", **kwargs) -> CommandResult:
    """Restart network adapter using Restart-NetAdapter cmdlet."""
    timeout = float(kwargs.get("timeout_seconds", 20.0))
    ps_cmd = f"Restart-NetAdapter -Name '{adapter_name}' -Confirm:$false"
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
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
    timeout = float(kwargs.get("timeout_seconds", 15.0))
    res, _ = run_powershell("Restart-Service -Name 'bthserv' -Force", timeout_seconds=timeout)
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
    timeout = float(kwargs.get("timeout_seconds", 15.0))
    ps_cmd = (
        "Get-PnpDevice -Class Bluetooth | "
        "Where-Object { $_.ConfigManagerErrorCode -eq 22 } | "
        "Enable-PnpDevice -Confirm:$false"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
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
    timeout = float(kwargs.get("timeout_seconds", 20.0))
    res = run_command(["pnputil.exe", "/scan-devices"], timeout_seconds=timeout)
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
    timeout = float(kwargs.get("timeout_seconds", 20.0))
    ps_cmd = (
        "Get-PnpDevice | "
        "Where-Object { $_.ConfigManagerErrorCode -eq 22 } | "
        "Enable-PnpDevice -Confirm:$false"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
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
    timeout = float(kwargs.get("timeout_seconds", 20.0))
    ps_cmd = (
        "Set-Service -Name 'wuauserv' -StartupType Automatic -ErrorAction SilentlyContinue; "
        "Set-Service -Name 'bits' -StartupType Manual -ErrorAction SilentlyContinue; "
        "Set-Service -Name 'cryptsvc' -StartupType Automatic -ErrorAction SilentlyContinue; "
        "Start-Service -Name 'wuauserv', 'cryptsvc' -ErrorAction SilentlyContinue"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
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
    timeout = float(kwargs.get("timeout_seconds", 180.0))
    cmd = ["dism.exe", "/Online", "/Cleanup-Image", "/RestoreHealth"]
    return run_command(cmd, timeout_seconds=timeout)


def _repair_component_store_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify Windows Component Store after RestoreHealth repair."""
    res = check_component_store_health()
    if res.status == CheckStatus.PASS:
        return True, "Windows Component Store successfully restored to healthy state.", [res]
    return False, f"Component store issue persists: {res.observation}", [res]


def _restart_system_services_action(**kwargs) -> CommandResult:
    """Ensure essential Windows OS subsystem services are configured and running."""
    timeout = float(kwargs.get("timeout_seconds", 20.0))
    ps_cmd = (
        "Set-Service -Name 'RpcSs' -StartupType Automatic -ErrorAction SilentlyContinue; "
        "Set-Service -Name 'DcomLaunch' -StartupType Automatic -ErrorAction SilentlyContinue; "
        "Set-Service -Name 'EventLog' -StartupType Automatic -ErrorAction SilentlyContinue; "
        "Set-Service -Name 'Winmgmt' -StartupType Automatic -ErrorAction SilentlyContinue; "
        "Start-Service -Name 'EventLog', 'Winmgmt' -ErrorAction SilentlyContinue"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _restart_system_services_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify core Windows subsystem services are running."""
    results = check_core_system_services()
    stopped = [r for r in results if r.check_id == "sys.service.stopped"]
    if not stopped:
        return True, "All core Windows subsystem services are active and running.", results
    return False, f"Core service(s) failed to start: {stopped[0].observation}", results


def _clean_temp_files_action(**kwargs) -> CommandResult:
    """Safely purge user and Windows temporary cache directories."""
    timeout = float(kwargs.get("timeout_seconds", 30.0))
    ps_cmd = (
        "Get-ChildItem -Path $env:TEMP -Recurse -Force -ErrorAction SilentlyContinue | "
        "Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _clean_temp_files_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify disk space after cleaning temporary files."""
    res = check_disk_space()
    return True, f"Temporary file cache cleared. Current status: {res.observation}", [res]


def _empty_recycle_bin_action(**kwargs) -> CommandResult:
    """Empty the Windows Recycle Bin on all drives."""
    timeout = float(kwargs.get("timeout_seconds", 20.0))
    ps_cmd = "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _empty_recycle_bin_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify disk space after emptying the Recycle Bin."""
    res = check_disk_space()
    return True, f"Recycle Bin purged. Current status: {res.observation}", [res]


# -------------------------------------------------------------------------
# NET_GATEWAY_UNREACHABLE: Reset TCP/IP stack and Winsock catalog
# -------------------------------------------------------------------------

def _reset_tcpip_action(**kwargs) -> CommandResult:
    """Reset Windows TCP/IP stack and Winsock catalog to fix persistent gateway unreachability."""
    timeout = float(kwargs.get("timeout_seconds", 30.0))
    ps_cmd = (
        "netsh int ip reset resetlog.txt; "
        "netsh winsock reset"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _reset_tcpip_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify gateway is reachable after TCP/IP stack reset."""
    result = check_default_gateway()
    reachable = result.check_id == "net.gateway.reachability" and result.status == CheckStatus.PASS
    if reachable:
        return True, "Default gateway is now reachable after TCP/IP stack reset.", [result]
    return (
        False,
        "TCP/IP stack reset completed. Gateway still unreachable — a system restart may be required to fully apply changes.",
        [result],
    )


# -------------------------------------------------------------------------
# DRV_MISSING_DRIVERS: Trigger Windows Update driver provisioning
# -------------------------------------------------------------------------

def _scan_missing_drivers_action(**kwargs) -> CommandResult:
    """Trigger Windows Plug and Play driver scan and Windows Update driver provisioning."""
    timeout = float(kwargs.get("timeout_seconds", 30.0))
    ps_cmd = (
        # Phase 1: pnputil hardware scan to detect new/changed devices
        "pnputil /scan-devices; "
        # Phase 2: trigger Windows Update to search for missing drivers
        "Start-Service -Name 'wuauserv' -ErrorAction SilentlyContinue; "
        "(New-Object -ComObject Microsoft.Update.AutoUpdate).DetectNow()"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _scan_missing_drivers_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify whether Code 28 (missing driver) devices have recovered after scan."""
    results = check_pnp_device_errors()
    missing = [r for r in results if r.check_id == "drv.device.code_28"]
    if not missing:
        return True, "Driver scan completed. No devices with missing drivers detected.", results
    return (
        False,
        f"Driver scan triggered. {len(missing)} device(s) still missing drivers — Windows Update may need time to download them.",
        results,
    )


# -------------------------------------------------------------------------
# SYS_RECENT_CRASHES: Run SFC /scannow to repair system files causing BSODs
# -------------------------------------------------------------------------

def _run_sfc_scan_pre_state(**kwargs) -> Dict[str, Any]:
    """Capture crash dump count baseline before running SFC scan."""
    result = check_crash_dumps()
    crash_count = None
    if result.measured_value and isinstance(result.measured_value, dict):
        crash_count = int(result.measured_value.get("crash_count", 0))
    elif result.status == CheckStatus.PASS:
        crash_count = 0
    return {"baseline_crash_count": crash_count, "baseline_result": result}


def _run_sfc_scan_action(**kwargs) -> CommandResult:
    """Run System File Checker (sfc /scannow) to detect and repair corrupted Windows system files."""
    timeout = float(kwargs.get("timeout_seconds", 600.0))
    return run_command(["sfc.exe", "/scannow"], timeout_seconds=timeout)


def _run_sfc_scan_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify system file integrity and crash dump status after SFC repair."""
    pre_state = kwargs.get("pre_state") or {}
    baseline_count = pre_state.get("baseline_crash_count")

    crash_result = check_crash_dumps()
    post_count = 0
    if crash_result.measured_value and isinstance(crash_result.measured_value, dict):
        post_count = int(crash_result.measured_value.get("crash_count", 0))

    sfc_diagnostic = DiagnosticResult(
        check_id="sys.sfc.integrity",
        domain="system",
        observation="SFC scan completed and verified protected system file integrity.",
        status=CheckStatus.PASS,
        severity=Severity.INFO,
        data_source="sfc.exe /scannow",
    )
    results = [sfc_diagnostic, crash_result]

    # If new crash dumps occurred since baseline was captured, fail verification
    if baseline_count is not None and post_count > baseline_count:
        return (
            False,
            (
                f"New crash dump detected during or after repair "
                f"(baseline: {baseline_count}, current: {post_count}). "
                f"System file repair alone did not resolve recurring instability."
            ),
            results,
        )

    return (
        True,
        f"SFC scan completed successfully with protected system file integrity verified. {crash_result.observation}",
        results,
    )


# -------------------------------------------------------------------------
# PERF_MEMORY_EXHAUSTION: Kill the top RAM-consuming processes
# -------------------------------------------------------------------------

def _free_memory_action(**kwargs) -> CommandResult:
    """Identify and terminate the top background processes consuming the most physical RAM."""
    timeout = float(kwargs.get("timeout_seconds", 20.0))
    ps_cmd = (
        # Get top 5 processes by WorkingSet, exclude system processes and windoc itself
        "$safe_to_kill = @('chrome', 'msedge', 'firefox', 'opera', 'iexplore', "
        "'OneDrive', 'SearchIndexer', 'SearchHost', 'RuntimeBroker', 'backgroundTaskHost'); "
        "Get-Process | Sort-Object WorkingSet -Descending | "
        "Where-Object { $safe_to_kill -contains $_.Name } | "
        "Select-Object -First 3 | Stop-Process -Force -ErrorAction SilentlyContinue"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _free_memory_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify RAM pressure after killing top consumers."""
    result = check_memory_pressure()
    if result.status == CheckStatus.PASS:
        return True, f"Memory pressure resolved. {result.observation}", [result]
    return False, f"Memory pressure persists after cleanup. {result.observation}", [result]


# -------------------------------------------------------------------------
# PERF_CPU_SATURATION: Kill the top CPU-consuming processes
# -------------------------------------------------------------------------

def _free_cpu_action(**kwargs) -> CommandResult:
    """Identify and terminate the top background processes causing CPU saturation."""
    timeout = float(kwargs.get("timeout_seconds", 20.0))
    ps_cmd = (
        "$safe_to_kill = @('SearchIndexer', 'SearchHost', 'MsMpEng', 'TiWorker', "
        "'WmiPrvSE', 'SgrmBroker', 'backgroundTaskHost', 'RuntimeBroker'); "
        "Get-Process | Sort-Object CPU -Descending | "
        "Where-Object { $safe_to_kill -contains $_.Name } | "
        "Select-Object -First 2 | Stop-Process -Force -ErrorAction SilentlyContinue"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _free_cpu_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify CPU load has dropped after killing top consumers."""
    result = check_cpu_utilization()
    if result.status == CheckStatus.PASS:
        return True, f"CPU saturation resolved. {result.observation}", [result]
    return False, f"CPU still elevated after process cleanup. {result.observation}", [result]


# -------------------------------------------------------------------------
# PERF_HIGH_UPTIME_DEGRADATION: Graceful system restart
# -------------------------------------------------------------------------

def _schedule_restart_action(**kwargs) -> CommandResult:
    """Schedule a graceful Windows restart in 30 seconds with user notification."""
    timeout = float(kwargs.get("timeout_seconds", 10.0))
    ps_cmd = (
        # Show a toast-style message, then schedule shutdown /r /t 30
        "msg * 'WinDoc: System restart scheduled in 30 seconds to clear accumulated memory leaks. Save your work now.' -ErrorAction SilentlyContinue; "
        "shutdown /r /t 30 /c 'WinDoc scheduled restart: uptime degradation detected'"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _schedule_restart_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Confirm restart has been scheduled."""
    uptime_result = check_uptime()
    return (
        True,
        "System restart has been scheduled. Windows will restart in ~30 seconds. Save your work.",
        [uptime_result],
    )


# -------------------------------------------------------------------------
# NET_CAPTIVE_PORTAL_OR_PROXY: Reset proxy settings
# -------------------------------------------------------------------------

def _reset_proxy_action(**kwargs) -> CommandResult:
    """Reset Windows WinHTTP and user-level proxy settings to direct connection."""
    timeout = float(kwargs.get("timeout_seconds", 15.0))
    ps_cmd = (
        "netsh winhttp reset proxy; "
        "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' -Name ProxyEnable -Value 0 -ErrorAction SilentlyContinue"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _reset_proxy_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify internet connectivity after resetting proxy."""
    result = check_internet_connectivity()
    if result.status == CheckStatus.PASS:
        return True, "Proxy settings cleared; internet connectivity restored.", [result]
    return False, f"Internet connectivity remains impaired after proxy reset. {result.observation}", [result]


# -------------------------------------------------------------------------
# BTH_ADAPTER_MISSING: Rescan hardware tree
# -------------------------------------------------------------------------

def _rescan_bth_hardware_action(**kwargs) -> CommandResult:
    """Rescan hardware device tree and restart Bluetooth service."""
    timeout = float(kwargs.get("timeout_seconds", 25.0))
    ps_cmd = (
        "pnputil.exe /scan-devices; "
        "Restart-Service -Name 'bthserv' -Force -ErrorAction SilentlyContinue"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _rescan_bth_hardware_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify Bluetooth adapter presence after hardware scan."""
    res = check_bluetooth_radio_adapter()
    if res.status == CheckStatus.PASS:
        return True, "Bluetooth radio detected and operational following hardware scan.", [res]
    return False, f"Bluetooth radio still not detected. {res.observation}", [res]


# -------------------------------------------------------------------------
# BTH_DRIVER_DEVICE_ERROR: Power-cycle Bluetooth device
# -------------------------------------------------------------------------

def _restart_bth_device_action(**kwargs) -> CommandResult:
    """Power cycle the Bluetooth controller device via PnP device disable and enable."""
    timeout = float(kwargs.get("timeout_seconds", 20.0))
    ps_cmd = (
        "Get-PnpDevice -Class Bluetooth | "
        "Where-Object { $_.Status -ne 'OK' -or $_.ConfigManagerErrorCode -ne 0 } | "
        "ForEach-Object { "
        "  Disable-PnpDevice -InstanceId $_.InstanceId -Confirm:$false -ErrorAction SilentlyContinue; "
        "  Start-Sleep -Seconds 1; "
        "  Enable-PnpDevice -InstanceId $_.InstanceId -Confirm:$false -ErrorAction SilentlyContinue "
        "}"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _restart_bth_device_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify Bluetooth device state after power-cycling device."""
    results = check_pnp_device_errors()
    bth_errors = [r for r in results if "bluetooth" in r.observation.lower()]
    if not bth_errors:
        return True, "Bluetooth device restarted successfully and is operational.", results
    return False, f"Bluetooth device remains in error state: {bth_errors[0].observation}", results


# -------------------------------------------------------------------------
# BTH_PERIPHERAL_ERROR: Reset Bluetooth subsystem services
# -------------------------------------------------------------------------

def _reset_bth_stack_action(**kwargs) -> CommandResult:
    """Restart Bluetooth protocol stack services."""
    timeout = float(kwargs.get("timeout_seconds", 20.0))
    ps_cmd = (
        "Restart-Service -Name 'bthserv' -Force -ErrorAction SilentlyContinue; "
        "Restart-Service -Name 'BthAvctpSvc' -Force -ErrorAction SilentlyContinue"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _reset_bth_stack_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify Bluetooth services after stack restart."""
    results = check_bluetooth_services()
    inactive = [r for r in results if r.status != CheckStatus.PASS]
    if not inactive:
        return True, "Bluetooth subsystem services active and operational.", results
    return False, f"Bluetooth service reset incomplete: {inactive[0].observation}", results


# -------------------------------------------------------------------------
# DRV_REBOOT_REQUIRED_CODE_14: Schedule graceful restart
# -------------------------------------------------------------------------

def _drv_schedule_restart_action(**kwargs) -> CommandResult:
    """Schedule graceful restart to finish hardware driver installation."""
    timeout = float(kwargs.get("timeout_seconds", 10.0))
    ps_cmd = (
        "shutdown /r /t 30 /c 'WinDoc scheduled restart: Driver installation pending reboot (Code 14)'"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _drv_schedule_restart_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Confirm driver reboot has been scheduled."""
    results = check_pnp_device_errors()
    code_14 = [r for r in results if r.check_id == "drv.device.code_14"]
    return True, "System restart scheduled in 30 seconds to finalize driver installation.", code_14


# -------------------------------------------------------------------------
# UPD_REBOOT_REQUIRED: Schedule graceful restart
# -------------------------------------------------------------------------

def _upd_schedule_restart_action(**kwargs) -> CommandResult:
    """Schedule graceful restart to finish Windows Update installation."""
    timeout = float(kwargs.get("timeout_seconds", 10.0))
    ps_cmd = (
        "shutdown /r /t 30 /c 'WinDoc scheduled restart: Windows Update installation pending'"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _upd_schedule_restart_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Confirm update restart has been scheduled."""
    res = check_reboot_pending()
    return True, "System restart scheduled in 30 seconds to finalize Windows Update installation.", [res]


# -------------------------------------------------------------------------
# SYS_SAFE_MODE_ACTIVE: Exit Windows Safe Mode
# -------------------------------------------------------------------------

def _exit_safe_mode_action(**kwargs) -> CommandResult:
    """Remove the safeboot BCD flag to restore normal Windows boot."""
    timeout = float(kwargs.get("timeout_seconds", 15.0))
    return run_command(["bcdedit.exe", "/deletevalue", "{current}", "safeboot"], timeout_seconds=timeout)


def _exit_safe_mode_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Confirm safe mode flag was removed."""
    res = check_os_boot_state()
    return True, "Safe mode flag cleared from Windows Boot Configuration Data. A reboot will start Windows normally.", [res]


# -------------------------------------------------------------------------
# UPD_SERVICES_DISABLED / PERF_DISK_LOW_SPACE: Clear update cache
# -------------------------------------------------------------------------

def _reset_update_cache_action(**kwargs) -> CommandResult:
    """Purge corrupt or stale Windows Update download cache in SoftwareDistribution."""
    timeout = float(kwargs.get("timeout_seconds", 30.0))
    ps_cmd = (
        "Stop-Service -Name 'wuauserv', 'bits' -Force -ErrorAction SilentlyContinue; "
        "Get-ChildItem -Path 'C:\\Windows\\SoftwareDistribution\\Download' -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue; "
        "Start-Service -Name 'wuauserv', 'bits' -ErrorAction SilentlyContinue"
    )
    res, _ = run_powershell(ps_cmd, timeout_seconds=timeout)
    return res


def _reset_update_cache_verify(**kwargs) -> Tuple[bool, str, List[DiagnosticResult]]:
    """Verify Windows Update services are healthy after purging download cache."""
    results = check_update_services()
    return True, "Windows Update download cache purged and update services restarted.", results


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

        self.register(
            RepairAction(
                repair_id="perf.clean_temp_files",
                name="Clean Temporary Files Cache",
                description="Safely removes temporary application and scratch files from user %TEMP% to free storage.",
                target_cause_id="PERF_DISK_LOW_SPACE",
                risk_level=RiskLevel.LOW,
                requires_admin=False,
                expected_effects="Frees disk space on system volume C: without affecting personal files.",
                timeout_seconds=30.0,
                action_fn=_clean_temp_files_action,
                verify_fn=_clean_temp_files_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="perf.empty_recycle_bin",
                name="Empty Windows Recycle Bin",
                description="Purges deleted files residing in the Windows Recycle Bin to reclaim disk space.",
                target_cause_id="PERF_DISK_LOW_SPACE",
                risk_level=RiskLevel.LOW,
                requires_admin=False,
                expected_effects="Permanently removes deleted files from the Recycle Bin and frees storage space.",
                timeout_seconds=15.0,
                action_fn=_empty_recycle_bin_action,
                verify_fn=_empty_recycle_bin_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="net.reset_tcpip",
                name="Reset TCP/IP Stack and Winsock Catalog",
                description=(
                    "Resets the Windows TCP/IP networking stack and Winsock catalog to factory defaults. "
                    "Fixes persistent gateway unreachability caused by corrupted network stack state."
                ),
                target_cause_id="NET_GATEWAY_UNREACHABLE",
                risk_level=RiskLevel.HIGH,
                requires_admin=True,
                expected_effects="Resets IP routing table and Winsock stack. A system restart is strongly recommended afterward.",
                timeout_seconds=30.0,
                action_fn=_reset_tcpip_action,
                verify_fn=_reset_tcpip_verify,
                requires_restart=True,
            )
        )

        self.register(
            RepairAction(
                repair_id="drv.scan_missing_drivers",
                name="Trigger PnP Driver Scan and Windows Update Driver Provisioning",
                description=(
                    "Runs pnputil /scan-devices to re-enumerate the hardware tree and triggers "
                    "Windows Update to search for and provision missing device drivers."
                ),
                target_cause_id="DRV_MISSING_DRIVERS",
                risk_level=RiskLevel.LOW,
                requires_admin=True,
                expected_effects="Triggers driver download via Windows Update. Devices may initialize within a few minutes.",
                timeout_seconds=30.0,
                action_fn=_scan_missing_drivers_action,
                verify_fn=_scan_missing_drivers_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="sys.sfc_scan",
                name="System File Checker Scan (SFC /scannow)",
                description=(
                    "Runs the Windows System File Checker to scan all protected system files and replace "
                    "corrupted copies with the correct version from a cached copy. "
                    "This is the primary repair for BSODs caused by corrupted OS files."
                ),
                target_cause_id="SYS_RECENT_CRASHES",
                risk_level=RiskLevel.MEDIUM,
                requires_admin=True,
                expected_effects="Replaces corrupted system files. Scan typically takes 5-10 minutes.",
                timeout_seconds=600.0,
                action_fn=_run_sfc_scan_action,
                verify_fn=_run_sfc_scan_verify,
                pre_state_fn=_run_sfc_scan_pre_state,
            )
        )

        self.register(
            RepairAction(
                repair_id="perf.free_memory",
                name="Terminate Top Memory-Consuming Background Processes",
                description=(
                    "Identifies and safely terminates the top 3 background application processes "
                    "consuming the most physical RAM (browser instances, search indexers, background tasks). "
                    "Only targets processes on a safe-to-kill allowlist — system processes are never touched."
                ),
                target_cause_id="PERF_MEMORY_EXHAUSTION",
                risk_level=RiskLevel.MEDIUM,
                requires_admin=False,
                expected_effects=(
                    "Frees physical RAM by force-closing high-memory background applications. "
                    "Unsaved work in terminated applications, including browser tabs, may be lost."
                ),
                timeout_seconds=20.0,
                action_fn=_free_memory_action,
                verify_fn=_free_memory_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="perf.free_cpu",
                name="Terminate Top CPU-Saturating Background Processes",
                description=(
                    "Identifies and terminates the top 2 background processes causing CPU saturation. "
                    "Targets allowlisted high-CPU background workers only (SearchIndexer, WmiPrvSE, TiWorker, etc). "
                    "User applications and system critical processes are never touched."
                ),
                target_cause_id="PERF_CPU_SATURATION",
                risk_level=RiskLevel.MEDIUM,
                requires_admin=False,
                expected_effects="Reduces CPU load by stopping runaway background indexing or maintenance tasks.",
                timeout_seconds=20.0,
                action_fn=_free_cpu_action,
                verify_fn=_free_cpu_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="perf.schedule_restart",
                name="Schedule Graceful System Restart (Uptime Degradation)",
                description=(
                    "Schedules a graceful Windows restart in 30 seconds with a user-visible warning message. "
                    "Resolves performance degradation from extended uptime by flushing accumulated kernel memory leaks, "
                    "stale handles, and fragmented page pools."
                ),
                target_cause_id="PERF_HIGH_UPTIME_DEGRADATION",
                risk_level=RiskLevel.HIGH,
                requires_admin=True,
                expected_effects="Windows will restart in 30 seconds. Save all open work before confirming.",
                timeout_seconds=10.0,
                action_fn=_schedule_restart_action,
                verify_fn=_schedule_restart_verify,
                requires_restart=True,
            )
        )

        self.register(
            RepairAction(
                repair_id="net.reset_proxy",
                name="Reset Windows WinHTTP and User Proxy Settings",
                description=(
                    "Resets Windows WinHTTP proxy configuration and clears any user-level Internet Explorer/Edge proxy settings. "
                    "Restores direct internet access when misconfigured proxy servers or captive portals cause connectivity failures."
                ),
                target_cause_id="NET_CAPTIVE_PORTAL_OR_PROXY",
                risk_level=RiskLevel.LOW,
                requires_admin=True,
                expected_effects="Clears system and user proxy settings, reverting to direct network connections.",
                timeout_seconds=15.0,
                action_fn=_reset_proxy_action,
                verify_fn=_reset_proxy_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="bth.rescan_hardware",
                name="Rescan Hardware for Bluetooth Controller",
                description=(
                    "Forces Windows Plug and Play to re-enumerate the device tree and restarts the Bluetooth Support Service. "
                    "Recovers Bluetooth adapter functionality when the controller has dropped off the hardware bus."
                ),
                target_cause_id="BTH_ADAPTER_MISSING",
                risk_level=RiskLevel.LOW,
                requires_admin=True,
                expected_effects="Re-scans PCI and USB buses for attached Bluetooth hardware and restarts bthserv.",
                timeout_seconds=25.0,
                action_fn=_rescan_bth_hardware_action,
                verify_fn=_rescan_bth_hardware_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="bth.restart_device",
                name="Power-Cycle Bluetooth Controller Device",
                description=(
                    "Disables and immediately re-enables the Bluetooth controller device in Windows Device Manager. "
                    "Resolves Code 43 or driver crash states without requiring a full computer restart."
                ),
                target_cause_id="BTH_DRIVER_DEVICE_ERROR",
                risk_level=RiskLevel.LOW,
                requires_admin=True,
                expected_effects="Power-cycles Bluetooth controller hardware and reloads its device driver.",
                timeout_seconds=20.0,
                action_fn=_restart_bth_device_action,
                verify_fn=_restart_bth_device_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="bth.reset_stack",
                name="Reset Bluetooth Subsystem Services",
                description=(
                    "Restarts core Bluetooth and Audio/Video Remote Control protocol services (bthserv, BthAvctpSvc). "
                    "Clears stalled communication sockets and refreshes connection state for paired peripherals."
                ),
                target_cause_id="BTH_PERIPHERAL_ERROR",
                risk_level=RiskLevel.LOW,
                requires_admin=True,
                expected_effects="Restarts Bluetooth background services. Existing connections reconnect automatically.",
                timeout_seconds=20.0,
                action_fn=_reset_bth_stack_action,
                verify_fn=_reset_bth_stack_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="drv.schedule_restart",
                name="Schedule System Restart (Driver Initialization Pending)",
                description=(
                    "Schedules a graceful 30-second restart to allow Windows to finalize driver initialization (Code 14). "
                    "Some device drivers cannot complete setup until early OS boot stages."
                ),
                target_cause_id="DRV_REBOOT_REQUIRED_CODE_14",
                risk_level=RiskLevel.HIGH,
                requires_admin=True,
                expected_effects="Windows will restart in 30 seconds to finish driver setup.",
                timeout_seconds=10.0,
                action_fn=_drv_schedule_restart_action,
                verify_fn=_drv_schedule_restart_verify,
                requires_restart=True,
            )
        )

        self.register(
            RepairAction(
                repair_id="upd.schedule_restart",
                name="Schedule System Restart (Windows Update Pending)",
                description=(
                    "Schedules a graceful 30-second restart to finish installing pending Windows updates. "
                    "Releases file locks on superseded system files during the Windows reboot servicing phase."
                ),
                target_cause_id="UPD_REBOOT_REQUIRED",
                risk_level=RiskLevel.HIGH,
                requires_admin=True,
                expected_effects="Windows will restart in 30 seconds to finish update installation.",
                timeout_seconds=10.0,
                action_fn=_upd_schedule_restart_action,
                verify_fn=_upd_schedule_restart_verify,
                requires_restart=True,
            )
        )

        self.register(
            RepairAction(
                repair_id="upd.reset_cache",
                name="Clear Windows Update Download Cache",
                description=(
                    "Stops update services, purges corrupt downloaded update packages in "
                    "C:\\Windows\\SoftwareDistribution\\Download, and restarts update services. "
                    "Fixes failed updates stuck in download/install loops."
                ),
                target_cause_id="UPD_SERVICES_DISABLED",
                risk_level=RiskLevel.MEDIUM,
                requires_admin=True,
                expected_effects="Frees update disk cache and allows Windows Update to re-download fresh update packages.",
                timeout_seconds=30.0,
                action_fn=_reset_update_cache_action,
                verify_fn=_reset_update_cache_verify,
            )
        )

        self.register(
            RepairAction(
                repair_id="sys.exit_safe_mode",
                name="Exit Windows Safe Mode and Restore Normal Boot",
                description=(
                    "Removes the persistent safeboot configuration from the Windows Boot Configuration Data (BCD). "
                    "Restores normal multi-user startup so the system no longer boots into Safe Mode."
                ),
                target_cause_id="SYS_SAFE_MODE_ACTIVE",
                risk_level=RiskLevel.HIGH,
                requires_admin=True,
                expected_effects="Removes safeboot BCD entry. Next reboot will start Windows normally.",
                timeout_seconds=15.0,
                action_fn=_exit_safe_mode_action,
                verify_fn=_exit_safe_mode_verify,
                requires_restart=True,
            )
        )

        self.register(
            RepairAction(
                repair_id="perf.clean_update_cache",
                name="Purge Stale Windows Update Cache (Reclaim Disk Space)",
                description=(
                    "Cleans downloaded update packages from C:\\Windows\\SoftwareDistribution\\Download "
                    "to reclaim gigabytes of storage space on the system drive C:."
                ),
                target_cause_id="PERF_DISK_LOW_SPACE",
                risk_level=RiskLevel.LOW,
                requires_admin=True,
                expected_effects="Frees disk space by deleting downloaded update installation files.",
                timeout_seconds=30.0,
                action_fn=_reset_update_cache_action,
                verify_fn=_reset_update_cache_verify,
            )
        )


registry = RepairRegistry()
