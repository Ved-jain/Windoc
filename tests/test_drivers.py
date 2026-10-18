"""Unit tests for the drivers and hardware devices diagnostic domain."""

from unittest.mock import patch

from windoc.core.engine import HypothesisStatus, evaluate_driver_hypotheses
from windoc.core.models import CheckStatus, DiagnosticResult
from windoc.core.runner import CommandResult
from windoc.domains.drivers.checks import (
    check_display_adapters,
    check_pnp_device_errors,
    check_usb_controllers,
    run_all_driver_checks,
)


def _make_cmd(exit_code: int = 0, stdout: str = "", stderr: str = "") -> CommandResult:
    return CommandResult(
        args=["powershell.exe"],
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_ms=5.0,
        timed_out=False,
        error=None,
    )


def test_check_pnp_devices_all_healthy() -> None:
    """Verify that when no PnP devices report error codes, PASS is returned."""
    mock_cmd = _make_cmd(exit_code=0)
    with patch("windoc.domains.drivers.checks.run_powershell", return_value=(mock_cmd, [])):
        results = check_pnp_device_errors()
        assert len(results) == 1
        assert results[0].check_id == "drv.pnp.all_healthy"
        assert results[0].status == CheckStatus.PASS


def test_check_pnp_devices_code_28_missing_driver() -> None:
    """Verify that Code 28 (Missing Driver) is mapped to drv.device.code_28 with FAIL status."""
    data = [
        {
            "FriendlyName": "PCI Simple Communications Controller",
            "InstanceId": "PCI\\VEN_8086&DEV_7A60",
            "Class": "System",
            "ConfigManagerErrorCode": 28,
            "Status": "Error",
        }
    ]
    mock_cmd = _make_cmd(exit_code=0)
    with patch("windoc.domains.drivers.checks.run_powershell", return_value=(mock_cmd, data)):
        results = check_pnp_device_errors()
        assert len(results) == 1
        assert results[0].check_id == "drv.device.code_28"
        assert results[0].status == CheckStatus.FAIL
        assert "missing installed drivers" in results[0].observation


def test_check_pnp_devices_code_43_hardware_stopped() -> None:
    """Verify that Code 43 (Device stopped) is mapped to drv.device.code_43 with FAIL status."""
    data = [
        {
            "FriendlyName": "Realtek PCIe GbE Family Controller",
            "InstanceId": "PCI\\VEN_10EC&DEV_8168",
            "Class": "Net",
            "ConfigManagerErrorCode": 43,
            "Status": "Error",
        }
    ]
    mock_cmd = _make_cmd(exit_code=0)
    with patch("windoc.domains.drivers.checks.run_powershell", return_value=(mock_cmd, data)):
        results = check_pnp_device_errors()
        assert len(results) == 1
        assert results[0].check_id == "drv.device.code_43"
        assert results[0].status == CheckStatus.FAIL
        assert "reported a problem" in results[0].observation


def test_check_pnp_devices_code_22_disabled() -> None:
    """Verify that Code 22 (Device disabled) is mapped to drv.device.code_22 with WARNING status."""
    data = [
        {
            "FriendlyName": "Intel Wireless Bluetooth",
            "InstanceId": "USB\\VID_8087&PID_0033",
            "Class": "Bluetooth",
            "ConfigManagerErrorCode": 22,
            "Status": "Error",
        }
    ]
    mock_cmd = _make_cmd(exit_code=0)
    with patch("windoc.domains.drivers.checks.run_powershell", return_value=(mock_cmd, data)):
        results = check_pnp_device_errors()
        assert len(results) == 1
        assert results[0].check_id == "drv.device.code_22"
        assert results[0].status == CheckStatus.WARNING
        assert "disabled in Windows" in results[0].observation


def test_check_display_adapters_operational() -> None:
    """Verify that operational display adapter reports PASS."""
    data = [
        {
            "FriendlyName": "Intel(R) UHD Graphics",
            "Status": "OK",
            "ConfigManagerErrorCode": 0,
        }
    ]
    mock_cmd = _make_cmd(exit_code=0)
    with patch("windoc.domains.drivers.checks.run_powershell", return_value=(mock_cmd, data)):
        result = check_display_adapters()
        assert result.check_id == "drv.display.adapter_state"
        assert result.status == CheckStatus.PASS
        assert "Display adapter operational" in result.observation


def test_check_usb_controllers_operational() -> None:
    """Verify that operational USB controllers report PASS."""
    data = [
        {
            "FriendlyName": "Intel USB 3.20 eXtensible Host Controller",
            "Status": "OK",
            "ConfigManagerErrorCode": 0,
        }
    ]
    mock_cmd = _make_cmd(exit_code=0)
    with patch("windoc.domains.drivers.checks.run_powershell", return_value=(mock_cmd, data)):
        result = check_usb_controllers()
        assert result.check_id == "drv.usb.controller_state"
        assert result.status == CheckStatus.PASS


def test_evaluate_drivers_healthy() -> None:
    """Verify that healthy evidence evaluates to DRV_ALL_HEALTHY."""
    evidence = [
        DiagnosticResult(
            check_id="drv.pnp.all_healthy",
            domain="drivers",
            observation="All devices operational",
            status=CheckStatus.PASS,
            data_source="Get-PnpDevice",
        ),
        DiagnosticResult(
            check_id="drv.display.adapter_state",
            domain="drivers",
            observation="GPU operational",
            status=CheckStatus.PASS,
            data_source="Get-PnpDevice",
        ),
    ]
    report = evaluate_driver_hypotheses(evidence)
    assert report.is_conclusive
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "DRV_ALL_HEALTHY"
    assert report.primary_finding.confidence == 1.0


def test_evaluate_drivers_missing_driver_code_28() -> None:
    """Verify that Code 28 evidence evaluates to DRV_MISSING_DRIVERS."""
    evidence = [
        DiagnosticResult(
            check_id="drv.device.code_28",
            domain="drivers",
            observation="Missing driver (Code 28)",
            status=CheckStatus.FAIL,
            data_source="Get-PnpDevice",
        )
    ]
    report = evaluate_driver_hypotheses(evidence)
    assert report.is_conclusive
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "DRV_MISSING_DRIVERS"
    assert report.primary_finding.confidence >= 0.95


def test_evaluate_drivers_device_crashed_code_43() -> None:
    """Verify that Code 43 evidence evaluates to DRV_DEVICE_CRASHED_CODE_43."""
    evidence = [
        DiagnosticResult(
            check_id="drv.device.code_43",
            domain="drivers",
            observation="Device stopped (Code 43)",
            status=CheckStatus.FAIL,
            data_source="Get-PnpDevice",
        )
    ]
    report = evaluate_driver_hypotheses(evidence)
    assert report.is_conclusive
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "DRV_DEVICE_CRASHED_CODE_43"
    assert report.primary_finding.confidence >= 0.90


def test_evaluate_drivers_device_disabled_code_22() -> None:
    """Verify that Code 22 evidence evaluates to DRV_DEVICE_DISABLED_CODE_22."""
    evidence = [
        DiagnosticResult(
            check_id="drv.device.code_22",
            domain="drivers",
            observation="Device disabled (Code 22)",
            status=CheckStatus.WARNING,
            data_source="Get-PnpDevice",
        )
    ]
    report = evaluate_driver_hypotheses(evidence)
    assert report.is_conclusive
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "DRV_DEVICE_DISABLED_CODE_22"
    assert report.primary_finding.confidence >= 0.90
