"""Read-only Bluetooth diagnostic checks for WinDoc."""

from typing import Any, Dict, List, Optional

from windoc.core.models import (
    CheckStatus,
    DiagnosticResult,
    ResultKind,
    Severity,
)
from windoc.core.runner import run_powershell


def check_bluetooth_services() -> List[DiagnosticResult]:
    """Inspect core Windows Bluetooth services (bthserv - Bluetooth Support Service)."""
    results: List[DiagnosticResult] = []

    ps_cmd = (
        "Get-Service -Name 'bthserv', 'BthHFSrv' -ErrorAction SilentlyContinue | "
        "Select-Object Name, DisplayName, Status, StartType"
    )
    cmd_result, services = run_powershell(ps_cmd, as_json=True, ensure_list=True)

    if not cmd_result.is_success or services is None:
        results.append(
            DiagnosticResult(
                check_id="bth.service.query",
                domain="bluetooth",
                observation=f"Failed to query Bluetooth services: {cmd_result.error or cmd_result.stderr}",
                status=CheckStatus.ERROR,
                severity=Severity.HIGH,
                data_source="Get-Service",
            )
        )
        return results

    bthserv_found = False
    for svc in services:
        name = svc.get("Name", "")
        display = svc.get("DisplayName", name)
        # Status can be integer (4 = Running, 1 = Stopped) or string ("Running")
        status_val = svc.get("Status")
        is_running = status_val in (4, "Running")
        start_type = svc.get("StartType", "")

        if name.lower() == "bthserv":
            bthserv_found = True
            if is_running:
                results.append(
                    DiagnosticResult(
                        check_id="bth.service.bthserv.state",
                        domain="bluetooth",
                        observation=f"Bluetooth Support Service ('{display}') is running.",
                        status=CheckStatus.PASS,
                        severity=Severity.INFO,
                        data_source="Get-Service",
                        measured_value={"name": name, "status": "Running", "start_type": start_type},
                    )
                )
            else:
                results.append(
                    DiagnosticResult(
                        check_id="bth.service.bthserv.state",
                        domain="bluetooth",
                        observation=f"Bluetooth Support Service ('{display}') is stopped (Status: {status_val}).",
                        status=CheckStatus.FAIL,
                        severity=Severity.HIGH,
                        data_source="Get-Service",
                        measured_value={"name": name, "status": status_val, "start_type": start_type},
                    )
                )

    if not bthserv_found:
        results.append(
            DiagnosticResult(
                check_id="bth.service.bthserv.state",
                domain="bluetooth",
                observation="Core Bluetooth Support Service (bthserv) not found on system.",
                status=CheckStatus.FAIL,
                severity=Severity.CRITICAL,
                data_source="Get-Service",
            )
        )

    return results


def check_bluetooth_radio_adapter() -> List[DiagnosticResult]:
    """Inspect the physical Bluetooth controller hardware, status, and Device Manager problem codes."""
    results: List[DiagnosticResult] = []

    ps_cmd = (
        "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | "
        "Select-Object FriendlyName, InstanceId, Status, Present, Problem, ConfigManagerErrorCode"
    )
    cmd_result, devices = run_powershell(ps_cmd, as_json=True, ensure_list=True)

    if not cmd_result.is_success or devices is None:
        results.append(
            DiagnosticResult(
                check_id="bth.adapter.query",
                domain="bluetooth",
                observation=f"Failed to query Bluetooth PnP devices: {cmd_result.error or cmd_result.stderr}",
                status=CheckStatus.ERROR,
                severity=Severity.HIGH,
                data_source="Get-PnpDevice",
            )
        )
        return results

    # Identify controller radio: ignore virtual enumerators and transport sub-devices
    controllers = []
    for d in devices:
        name = d.get("FriendlyName", "")
        # Enumerators and protocol drivers are virtual abstractions, not the hardware radio
        if any(v in name for v in ["Enumerator", "Protocol TDI", "Transport"]):
            continue
        # True radios typically have "Bluetooth" or "Wireless" in name and are controller class
        if "Bluetooth" in name or "Wireless" in name:
            controllers.append(d)

    if not controllers:
        results.append(
            DiagnosticResult(
                check_id="bth.adapter.presence",
                domain="bluetooth",
                observation="No physical Bluetooth controller hardware detected on the system.",
                status=CheckStatus.FAIL,
                severity=Severity.CRITICAL,
                data_source="Get-PnpDevice",
                result_kind=ResultKind.CONFIRMED,
            )
        )
        return results

    for ctrl in controllers:
        name = ctrl.get("FriendlyName", "Unknown Controller")
        instance_id = ctrl.get("InstanceId", "")
        code = ctrl.get("ConfigManagerErrorCode", 0)
        status = ctrl.get("Status", "Unknown")
        present = ctrl.get("Present", True)

        if code == 0 and status == "OK":
            results.append(
                DiagnosticResult(
                    check_id="bth.adapter.operational",
                    domain="bluetooth",
                    observation=f"Bluetooth controller '{name}' is operational (Status: OK).",
                    status=CheckStatus.PASS,
                    severity=Severity.INFO,
                    data_source="Get-PnpDevice",
                    measured_value={"name": name, "instance_id": instance_id, "error_code": 0},
                )
            )
        elif code == 22:
            # Code 22: Device is administratively disabled
            results.append(
                DiagnosticResult(
                    check_id="bth.adapter.disabled",
                    domain="bluetooth",
                    observation=f"Bluetooth controller '{name}' is administratively disabled (Code 22).",
                    status=CheckStatus.WARNING,
                    severity=Severity.MEDIUM,
                    data_source="Get-PnpDevice",
                    error_code="Code 22 (CM_PROB_DISABLED)",
                    measured_value={"name": name, "instance_id": instance_id, "error_code": 22},
                )
            )
        elif code in (10, 43):
            # Code 10 / 43: Driver initialization or hardware error
            results.append(
                DiagnosticResult(
                    check_id="bth.adapter.driver_error",
                    domain="bluetooth",
                    observation=f"Bluetooth controller '{name}' reported hardware/driver failure (Code {code}).",
                    status=CheckStatus.FAIL,
                    severity=Severity.HIGH,
                    data_source="Get-PnpDevice",
                    error_code=f"Code {code}",
                    measured_value={"name": name, "instance_id": instance_id, "error_code": code},
                )
            )
        else:
            results.append(
                DiagnosticResult(
                    check_id="bth.adapter.state",
                    domain="bluetooth",
                    observation=f"Bluetooth controller '{name}' status: {status} (Code {code}).",
                    status=CheckStatus.WARNING,
                    severity=Severity.LOW,
                    data_source="Get-PnpDevice",
                    measured_value={"name": name, "instance_id": instance_id, "error_code": code},
                )
            )

    return results


def check_bluetooth_peripherals() -> List[DiagnosticResult]:
    """Inspect paired Bluetooth peripherals, isolating peripheral issues from adapter-level health."""
    results: List[DiagnosticResult] = []

    ps_cmd = (
        "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | "
        "Where-Object { $_.FriendlyName -notlike '*Enumerator*' -and $_.FriendlyName -notlike '*Protocol TDI*' -and $_.FriendlyName -notlike '*Adapter*' -and $_.FriendlyName -notlike '*Wireless Bluetooth*' } | "
        "Select-Object FriendlyName, Status, Present, ConfigManagerErrorCode"
    )
    cmd_result, peripherals = run_powershell(ps_cmd, as_json=True, ensure_list=True)

    if not cmd_result.is_success or peripherals is None:
        return results

    # Filter unique device names (AVRCP transports create duplicate entries for one audio peripheral)
    seen_names = set()
    unique_devices = []
    for p in peripherals:
        raw_name = p.get("FriendlyName", "").replace(" Avrcp Transport", "").strip()
        if raw_name and raw_name not in seen_names:
            seen_names.add(raw_name)
            unique_devices.append((raw_name, p))

    if not unique_devices:
        results.append(
            DiagnosticResult(
                check_id="bth.peripherals.summary",
                domain="bluetooth",
                observation="No paired Bluetooth peripherals configured on the system.",
                status=CheckStatus.PASS,
                severity=Severity.INFO,
                data_source="Get-PnpDevice",
            )
        )
        return results

    connected_count = 0
    error_count = 0

    for name, dev in unique_devices:
        present = dev.get("Present", False)
        code = dev.get("ConfigManagerErrorCode", 0)
        status = dev.get("Status", "Unknown")

        if present and status == "OK" and code == 0:
            connected_count += 1
        elif code not in (0, 45):  # 45 means offline/disconnected, which is normal for turned-off peripherals
            error_count += 1
            results.append(
                DiagnosticResult(
                    check_id=f"bth.peripheral.{name.lower().replace(' ', '_')}.error",
                    domain="bluetooth",
                    observation=f"Paired device '{name}' reported problem code: {code} (Status: {status}).",
                    status=CheckStatus.WARNING,
                    severity=Severity.LOW,
                    data_source="Get-PnpDevice",
                    measured_value={"name": name, "error_code": code},
                )
            )

    results.append(
        DiagnosticResult(
            check_id="bth.peripherals.summary",
            domain="bluetooth",
            observation=f"Discovered {len(unique_devices)} paired device(s); {connected_count} actively connected.",
            status=CheckStatus.PASS,
            severity=Severity.INFO,
            data_source="Get-PnpDevice",
            measured_value={"total": len(unique_devices), "connected": connected_count, "errors": error_count},
        )
    )

    return results


def run_all_bluetooth_checks() -> List[DiagnosticResult]:
    """Execute all Bluetooth diagnostic checks across services, adapter radio, and peripherals."""
    evidence: List[DiagnosticResult] = []
    evidence.extend(check_bluetooth_services())
    evidence.extend(check_bluetooth_radio_adapter())
    evidence.extend(check_bluetooth_peripherals())
    return evidence
