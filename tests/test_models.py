"""Unit tests for diagnostic result models."""

import pytest
from pydantic import ValidationError

from windoc.core.models import (
    CheckStatus,
    DiagnosticResult,
    ResultKind,
    Severity,
)


def test_diagnostic_result_creation_and_defaults() -> None:
    """Verify that DiagnosticResult populates defaults properly."""
    result = DiagnosticResult(
        check_id="net.adapter.state",
        domain="network",
        observation="Wi-Fi adapter is disconnected",
        status=CheckStatus.FAIL,
    )

    assert result.check_id == "net.adapter.state"
    assert result.domain == "network"
    assert result.status == CheckStatus.FAIL
    assert result.severity == Severity.INFO
    assert result.result_kind == ResultKind.OBSERVATION
    assert result.admin_required is False
    assert result.admin_available is False
    assert result.timestamp is not None


def test_diagnostic_result_immutability() -> None:
    """DiagnosticResult should be immutable once recorded."""
    result = DiagnosticResult(
        check_id="net.dns.resolution",
        domain="network",
        observation="DNS resolved correctly",
        status=CheckStatus.PASS,
    )
    with pytest.raises(ValidationError):
        result.status = CheckStatus.FAIL  # type: ignore[misc]


def test_diagnostic_result_invalid_enum() -> None:
    """Invalid check status strings should trigger validation error."""
    with pytest.raises(ValidationError):
        DiagnosticResult(
            check_id="net.test",
            domain="network",
            observation="Invalid status check",
            status="INVALID_STATUS",  # type: ignore[arg-type]
        )


def test_diagnostic_result_json_roundtrip() -> None:
    """Ensure DiagnosticResult can be serialized to JSON and reconstructed."""
    original = DiagnosticResult(
        check_id="net.ip.dhcp",
        domain="network",
        observation="DHCP assigned valid address",
        status=CheckStatus.PASS,
        severity=Severity.LOW,
        result_kind=ResultKind.CONFIRMED,
        measured_value={"ip": "192.168.1.100", "gateway": "192.168.1.1"},
        data_source="Get-NetIPConfiguration",
    )
    json_str = original.model_dump_json()
    reconstructed = DiagnosticResult.model_validate_json(json_str)

    assert reconstructed.check_id == original.check_id
    assert reconstructed.status == original.status
    assert reconstructed.measured_value == original.measured_value
    assert reconstructed.data_source == original.data_source
