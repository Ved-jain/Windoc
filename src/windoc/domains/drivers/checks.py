"""Diagnostic checks for Windows Device Manager, hardware drivers, and PnP devices."""

from typing import Any, Dict, List

from windoc.core.models import CheckStatus, DiagnosticResult, ResultKind, Severity
from windoc.core.runner import run_powershell


def check_pnp_device_errors() -> List[DiagnosticResult]:
    """Check for any active, connected PnP devices reporting Device Manager error codes.

    Filters out ConfigManagerErrorCode 45 ('Device not connected/present') to avoid
    flagging disconnected peripherals or powered-off accessories.
    """
    ps_cmd = (
        "Get-PnpDevice | "
        "Where-Object { $_.Present -eq $true -and $_.ConfigManagerErrorCode -ne 0 -and $_.ConfigManagerErrorCode -ne 45 } | "
        "Select-Object FriendlyName, InstanceId, Class, ConfigManagerErrorCode, Status"
    )
    cmd_res, raw_data = run_powershell(ps_cmd, as_json=True, ensure_list=True, timeout_seconds=15.0)

    if not cmd_res.is_success:
        return [
            DiagnosticResult(
                check_id="drv.pnp.device_query",
                domain="drivers",
                observation=f"Failed to query PnP devices via PowerShell: {cmd_res.error or cmd_res.stderr or 'Unknown error'}",
                status=CheckStatus.ERROR,
                severity=Severity.HIGH,
                data_source="Get-PnpDevice",
                measured_value={"exit_code": cmd_res.exit_code},
            )
        ]

    devices: List[Dict[str, Any]] = raw_data or []
    if not devices:
        return [
            DiagnosticResult(
                check_id="drv.pnp.all_healthy",
                domain="drivers",
                observation="All active hardware devices are operational (0 Device Manager error codes).",
                status=CheckStatus.PASS,
                severity=Severity.INFO,
                data_source="Get-PnpDevice",
                measured_value={"error_device_count": 0},
            )
        ]

    results: List[DiagnosticResult] = []
    for dev in devices:
        name = dev.get("FriendlyName") or "Unknown Device"
        instance_id = dev.get("InstanceId", "")
        error_code = dev.get("ConfigManagerErrorCode", 0)
        dev_class = dev.get("Class") or "Unknown"

        if error_code == 28:
            results.append(
                DiagnosticResult(
                    check_id="drv.device.code_28",
                    domain="drivers",
                    observation=f"Device '{name}' ({dev_class}) is missing installed drivers (Code 28).",
                    status=CheckStatus.FAIL,
                    severity=Severity.HIGH,
                    result_kind=ResultKind.OBSERVATION,
                    data_source="Get-PnpDevice",
                    measured_value={"instance_id": instance_id, "error_code": 28, "class": dev_class},
                )
            )
        elif error_code == 43:
            results.append(
                DiagnosticResult(
                    check_id="drv.device.code_43",
                    domain="drivers",
                    observation=f"Device '{name}' was stopped by Windows because it reported a problem (Code 43).",
                    status=CheckStatus.FAIL,
                    severity=Severity.HIGH,
                    result_kind=ResultKind.OBSERVATION,
                    data_source="Get-PnpDevice",
                    measured_value={"instance_id": instance_id, "error_code": 43, "class": dev_class},
                )
            )
        elif error_code == 22:
            results.append(
                DiagnosticResult(
                    check_id="drv.device.code_22",
                    domain="drivers",
                    observation=f"Device '{name}' is currently disabled in Windows (Code 22).",
                    status=CheckStatus.WARNING,
                    severity=Severity.MEDIUM,
                    result_kind=ResultKind.OBSERVATION,
                    data_source="Get-PnpDevice",
                    measured_value={"instance_id": instance_id, "error_code": 22, "class": dev_class},
                )
            )
        elif error_code == 14:
            results.append(
                DiagnosticResult(
                    check_id="drv.device.code_14",
                    domain="drivers",
                    observation=f"Device '{name}' requires a computer restart to complete driver initialization (Code 14).",
                    status=CheckStatus.WARNING,
                    severity=Severity.MEDIUM,
                    result_kind=ResultKind.OBSERVATION,
                    data_source="Get-PnpDevice",
                    measured_value={"instance_id": instance_id, "error_code": 14, "class": dev_class},
                )
            )
        elif error_code == 10:
            results.append(
                DiagnosticResult(
                    check_id="drv.device.code_10",
                    domain="drivers",
                    observation=f"Device '{name}' cannot start (Code 10).",
                    status=CheckStatus.FAIL,
                    severity=Severity.HIGH,
                    result_kind=ResultKind.OBSERVATION,
                    data_source="Get-PnpDevice",
                    measured_value={"instance_id": instance_id, "error_code": 10, "class": dev_class},
                )
            )
        else:
            results.append(
                DiagnosticResult(
                    check_id="drv.device.code_generic",
                    domain="drivers",
                    observation=f"Device '{name}' is in error state (Code {error_code}).",
                    status=CheckStatus.WARNING,
                    severity=Severity.MEDIUM,
                    result_kind=ResultKind.OBSERVATION,
                    data_source="Get-PnpDevice",
                    measured_value={"instance_id": instance_id, "error_code": error_code, "class": dev_class},
                )
            )

    return results


def check_display_adapters() -> DiagnosticResult:
    """Verify that at least one display adapter (GPU) is present and operational."""
    ps_cmd = (
        "Get-PnpDevice -Class 'Display' | "
        "Where-Object { $_.Present -eq $true } | "
        "Select-Object FriendlyName, Status, ConfigManagerErrorCode"
    )
    cmd_res, raw_data = run_powershell(ps_cmd, as_json=True, ensure_list=True, timeout_seconds=10.0)

    if not cmd_res.is_success:
        return DiagnosticResult(
            check_id="drv.display.adapter_state",
            domain="drivers",
            observation=f"Failed to query display adapters: {cmd_res.error or cmd_res.stderr or 'Unknown error'}",
            status=CheckStatus.ERROR,
            severity=Severity.HIGH,
            data_source="Get-PnpDevice -Class Display",
        )

    gpus: List[Dict[str, Any]] = raw_data or []
    if not gpus:
        return DiagnosticResult(
            check_id="drv.display.adapter_state",
            domain="drivers",
            observation="No active display adapter detected.",
            status=CheckStatus.FAIL,
            severity=Severity.CRITICAL,
            data_source="Get-PnpDevice -Class Display",
        )

    operational = [g for g in gpus if g.get("Status") == "OK" and g.get("ConfigManagerErrorCode") == 0]
    names = ", ".join(g.get("FriendlyName", "GPU") for g in gpus)

    if operational:
        return DiagnosticResult(
            check_id="drv.display.adapter_state",
            domain="drivers",
            observation=f"Display adapter operational ({len(operational)} active GPU(s): {names}).",
            status=CheckStatus.PASS,
            severity=Severity.INFO,
            data_source="Get-PnpDevice -Class Display",
            measured_value={"gpus": gpus},
        )

    return DiagnosticResult(
        check_id="drv.display.adapter_state",
        domain="drivers",
        observation=f"All detected display adapters are reporting errors: {names}",
        status=CheckStatus.FAIL,
        severity=Severity.HIGH,
        data_source="Get-PnpDevice -Class Display",
        metadata={"gpus": gpus},
    )


def check_usb_controllers() -> DiagnosticResult:
    """Verify that USB host controllers are present and operational."""
    ps_cmd = (
        "Get-PnpDevice -Class 'USB' | "
        "Where-Object { $_.Present -eq $true } | "
        "Select-Object FriendlyName, Status, ConfigManagerErrorCode"
    )
    cmd_res, raw_data = run_powershell(ps_cmd, as_json=True, ensure_list=True, timeout_seconds=10.0)

    if not cmd_res.is_success:
        return DiagnosticResult(
            check_id="drv.usb.controller_state",
            domain="drivers",
            observation=f"Failed to query USB controllers: {cmd_res.error or cmd_res.stderr or 'Unknown error'}",
            status=CheckStatus.ERROR,
            severity=Severity.MEDIUM,
            data_source="Get-PnpDevice -Class USB",
        )

    controllers: List[Dict[str, Any]] = raw_data or []
    if not controllers:
        return DiagnosticResult(
            check_id="drv.usb.controller_state",
            domain="drivers",
            observation="No active USB host controllers found.",
            status=CheckStatus.WARNING,
            severity=Severity.MEDIUM,
            data_source="Get-PnpDevice -Class USB",
        )

    controllers_with_error = [c for c in controllers if c.get("ConfigManagerErrorCode", 0) != 0]

    if not controllers_with_error:
        return DiagnosticResult(
            check_id="drv.usb.controller_state",
            domain="drivers",
            observation=f"All {len(controllers)} active USB controller(s) are operational.",
            status=CheckStatus.PASS,
            severity=Severity.INFO,
            data_source="Get-PnpDevice -Class USB",
        )

    bad_names = ", ".join(c.get("FriendlyName", "USB Device") for c in controllers_with_error)
    return DiagnosticResult(
        check_id="drv.usb.controller_state",
        domain="drivers",
        observation=f"{len(controllers_with_error)} USB controller(s) reporting errors: {bad_names}",
        status=CheckStatus.WARNING,
        severity=Severity.MEDIUM,
        data_source="Get-PnpDevice -Class USB",
        measured_value={"faulty_controllers": controllers_with_error},
    )


def run_all_driver_checks() -> List[DiagnosticResult]:
    """Execute all driver and hardware device diagnostic checks."""
    results: List[DiagnosticResult] = []
    results.extend(check_pnp_device_errors())
    results.append(check_display_adapters())
    results.append(check_usb_controllers())
    return results
