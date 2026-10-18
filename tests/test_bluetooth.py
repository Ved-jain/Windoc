"""Unit tests for Bluetooth diagnostics and hypothesis evaluation."""

from unittest.mock import patch
import pytest

from windoc.core.engine import HypothesisStatus, evaluate_bluetooth_hypotheses
from windoc.core.models import CheckStatus, DiagnosticResult, Severity
from windoc.core.runner import CommandResult
from windoc.domains.bluetooth.checks import (
    check_bluetooth_peripherals,
    check_bluetooth_radio_adapter,
    check_bluetooth_services,
    run_all_bluetooth_checks,
)


def test_check_bluetooth_services_running() -> None:
    """Verify that a running bthserv service produces a PASS result."""
    mock_svc = [
        {"Name": "bthserv", "DisplayName": "Bluetooth Support Service", "Status": 4, "StartType": 3}
    ]
    with patch("windoc.domains.bluetooth.checks.run_powershell") as mock_ps:
        mock_ps.return_value = (CommandResult(args=[], exit_code=0), mock_svc)
        results = check_bluetooth_services()

        assert len(results) == 1
        assert results[0].check_id == "bth.service.bthserv.state"
        assert results[0].status == CheckStatus.PASS
        assert "running" in results[0].observation


def test_check_bluetooth_services_stopped() -> None:
    """Verify that a stopped bthserv service produces a FAIL result."""
    mock_svc = [
        {"Name": "bthserv", "DisplayName": "Bluetooth Support Service", "Status": 1, "StartType": 3}
    ]
    with patch("windoc.domains.bluetooth.checks.run_powershell") as mock_ps:
        mock_ps.return_value = (CommandResult(args=[], exit_code=0), mock_svc)
        results = check_bluetooth_services()

        assert len(results) == 1
        assert results[0].status == CheckStatus.FAIL
        assert results[0].severity == Severity.HIGH
        assert "stopped" in results[0].observation


def test_check_bluetooth_radio_adapter_operational() -> None:
    """Verify operational controller detection (Status OK, Code 0)."""
    mock_devices = [
        {"FriendlyName": "Microsoft Bluetooth Enumerator", "Status": "OK", "ConfigManagerErrorCode": 0},
        {"FriendlyName": "Intel(R) Wireless Bluetooth(R)", "Status": "OK", "ConfigManagerErrorCode": 0, "InstanceId": "USB\\VID_8087"},
    ]
    with patch("windoc.domains.bluetooth.checks.run_powershell") as mock_ps:
        mock_ps.return_value = (CommandResult(args=[], exit_code=0), mock_devices)
        results = check_bluetooth_radio_adapter()

        assert len(results) == 1
        assert results[0].check_id == "bth.adapter.operational"
        assert results[0].status == CheckStatus.PASS


def test_check_bluetooth_radio_adapter_disabled_code_22() -> None:
    """Verify administratively disabled controller detection (Code 22)."""
    mock_devices = [
        {"FriendlyName": "Realtek Bluetooth Adapter", "Status": "Error", "ConfigManagerErrorCode": 22, "InstanceId": "USB\\VID_0BDA"},
    ]
    with patch("windoc.domains.bluetooth.checks.run_powershell") as mock_ps:
        mock_ps.return_value = (CommandResult(args=[], exit_code=0), mock_devices)
        results = check_bluetooth_radio_adapter()

        assert len(results) == 1
        assert results[0].check_id == "bth.adapter.disabled"
        assert results[0].status == CheckStatus.WARNING
        assert "disabled" in results[0].observation


def test_check_bluetooth_radio_adapter_code_43() -> None:
    """Verify controller hardware/driver error detection (Code 43)."""
    mock_devices = [
        {"FriendlyName": "Intel(R) Wireless Bluetooth(R)", "Status": "Error", "ConfigManagerErrorCode": 43, "InstanceId": "USB\\VID_8087"},
    ]
    with patch("windoc.domains.bluetooth.checks.run_powershell") as mock_ps:
        mock_ps.return_value = (CommandResult(args=[], exit_code=0), mock_devices)
        results = check_bluetooth_radio_adapter()

        assert len(results) == 1
        assert results[0].check_id == "bth.adapter.driver_error"
        assert results[0].status == CheckStatus.FAIL


def test_check_bluetooth_radio_adapter_missing() -> None:
    """Verify when no physical Bluetooth radio hardware is found."""
    with patch("windoc.domains.bluetooth.checks.run_powershell") as mock_ps:
        mock_ps.return_value = (CommandResult(args=[], exit_code=0), [])
        results = check_bluetooth_radio_adapter()

        assert len(results) == 1
        assert results[0].check_id == "bth.adapter.presence"
        assert results[0].status == CheckStatus.FAIL
        assert results[0].severity == Severity.CRITICAL


def test_evaluate_bluetooth_healthy() -> None:
    """Verify that passing service and adapter checks confirm BTH_ALL_HEALTHY."""
    evidence = [
        DiagnosticResult(
            check_id="bth.service.bthserv.state",
            domain="bluetooth",
            observation="Bluetooth Support Service is running",
            status=CheckStatus.PASS,
        ),
        DiagnosticResult(
            check_id="bth.adapter.operational",
            domain="bluetooth",
            observation="Bluetooth controller is operational",
            status=CheckStatus.PASS,
        ),
    ]
    report = evaluate_bluetooth_hypotheses(evidence)
    assert report.is_conclusive is True
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "BTH_ALL_HEALTHY"
    assert report.primary_finding.status == HypothesisStatus.CONFIRMED


def test_evaluate_bluetooth_service_stopped() -> None:
    """Verify that stopped service diagnoses BTH_SERVICE_STOPPED."""
    evidence = [
        DiagnosticResult(
            check_id="bth.service.bthserv.state",
            domain="bluetooth",
            observation="bthserv is stopped",
            status=CheckStatus.FAIL,
        ),
        DiagnosticResult(
            check_id="bth.adapter.operational",
            domain="bluetooth",
            observation="Adapter operational",
            status=CheckStatus.PASS,
        ),
    ]
    report = evaluate_bluetooth_hypotheses(evidence)
    assert report.is_conclusive is True
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "BTH_SERVICE_STOPPED"


def test_evaluate_bluetooth_adapter_disabled() -> None:
    """Verify that Code 22 diagnoses BTH_ADAPTER_DISABLED."""
    evidence = [
        DiagnosticResult(
            check_id="bth.service.bthserv.state",
            domain="bluetooth",
            observation="bthserv is running",
            status=CheckStatus.PASS,
        ),
        DiagnosticResult(
            check_id="bth.adapter.disabled",
            domain="bluetooth",
            observation="Controller disabled Code 22",
            status=CheckStatus.WARNING,
        ),
    ]
    report = evaluate_bluetooth_hypotheses(evidence)
    assert report.is_conclusive is True
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "BTH_ADAPTER_DISABLED"


def test_evaluate_bluetooth_adapter_missing() -> None:
    """Verify missing adapter diagnoses BTH_ADAPTER_MISSING."""
    evidence = [
        DiagnosticResult(
            check_id="bth.adapter.presence",
            domain="bluetooth",
            observation="No Bluetooth hardware detected",
            status=CheckStatus.FAIL,
        ),
    ]
    report = evaluate_bluetooth_hypotheses(evidence)
    assert report.is_conclusive is True
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "BTH_ADAPTER_MISSING"
