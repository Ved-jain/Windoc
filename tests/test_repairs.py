"""Unit tests for the controlled repair subsystem."""

from unittest.mock import MagicMock, patch
import pytest

from windoc.core.models import CheckStatus, DiagnosticResult
from windoc.core.runner import CommandResult
from windoc.repairs.executor import execute_repair
from windoc.repairs.models import RepairStatus, RiskLevel
from windoc.repairs.registry import RepairAction, registry


def test_repair_registry_defaults() -> None:
    """Verify that expected default repairs are registered and discoverable."""
    all_repairs = registry.list_all()
    assert len(all_repairs) >= 3

    dns_repair = registry.get("net.flush_dns")
    assert dns_repair is not None
    assert dns_repair.target_cause_id == "NET_DNS_RESOLUTION_FAILED"
    assert dns_repair.risk_level == RiskLevel.LOW
    assert dns_repair.requires_admin is False

    matching = registry.find_for_cause("NET_DNS_RESOLUTION_FAILED")
    assert len(matching) == 1
    assert matching[0].repair_id == "net.flush_dns"


def test_repair_user_declines_consent() -> None:
    """Verify that declining interactive confirmation safely aborts without running commands."""
    action_mock = MagicMock()
    custom_repair = RepairAction(
        repair_id="test.repair",
        name="Test Action",
        description="Testing user consent abort",
        target_cause_id="TEST_CAUSE",
        risk_level=RiskLevel.LOW,
        requires_admin=False,
        expected_effects="None",
        timeout_seconds=5.0,
        action_fn=action_mock,
        verify_fn=lambda **kw: (True, "OK", []),
    )

    result = execute_repair(custom_repair, auto_approve=False, prompt_fn=lambda _: False)
    assert result.status == RepairStatus.ABORTED
    assert action_mock.called is False


def test_repair_permission_denied() -> None:
    """Verify that privileged repairs abort if administrator privileges are not present."""
    privileged_repair = RepairAction(
        repair_id="test.privileged",
        name="Admin Action",
        description="Testing admin check",
        target_cause_id="TEST_CAUSE",
        risk_level=RiskLevel.MEDIUM,
        requires_admin=True,
        expected_effects="None",
        timeout_seconds=5.0,
        action_fn=lambda **kw: CommandResult(args=[], exit_code=0),
        verify_fn=lambda **kw: (True, "OK", []),
    )

    with patch("windoc.repairs.executor.check_is_admin", return_value=False):
        result = execute_repair(privileged_repair, auto_approve=True)
        assert result.status == RepairStatus.PERMISSION_DENIED
        assert "requires Administrator privileges" in result.message


def test_repair_command_failure() -> None:
    """Verify handling when the underlying repair command returns a non-zero exit code."""
    failing_repair = RepairAction(
        repair_id="test.fail",
        name="Failing Command",
        description="Testing command error",
        target_cause_id="TEST_CAUSE",
        risk_level=RiskLevel.LOW,
        requires_admin=False,
        expected_effects="None",
        timeout_seconds=5.0,
        action_fn=lambda **kw: CommandResult(args=["bad_cmd"], exit_code=1, stderr="Subprocess error"),
        verify_fn=lambda **kw: (True, "OK", []),
    )

    result = execute_repair(failing_repair, auto_approve=True)
    assert result.status == RepairStatus.FAILED
    assert "exited with code 1" in result.message


def test_repair_success_and_verified() -> None:
    """Verify that execution + successful verification returns SUCCESS."""
    success_repair = RepairAction(
        repair_id="test.success",
        name="Successful Repair",
        description="Testing successful repair flow",
        target_cause_id="TEST_CAUSE",
        risk_level=RiskLevel.LOW,
        requires_admin=False,
        expected_effects="None",
        timeout_seconds=5.0,
        action_fn=lambda **kw: CommandResult(args=["cmd"], exit_code=0, stdout="Success"),
        verify_fn=lambda **kw: (True, "Original symptom resolved", []),
    )

    result = execute_repair(success_repair, auto_approve=True)
    assert result.status == RepairStatus.SUCCESS
    assert result.verified is True
    assert "Original symptom resolved" in result.message


def test_repair_verification_failed_despite_exit_zero() -> None:
    """CRITICAL: Command exited with 0, but independent verification proved the problem persists.
    
    This ensures WinDoc never falsely claims a problem is resolved just because
    a shell utility exited without error.
    """
    deceptive_repair = RepairAction(
        repair_id="test.deceptive",
        name="Deceptive Command",
        description="Command returns 0, but problem still exists",
        target_cause_id="TEST_CAUSE",
        risk_level=RiskLevel.LOW,
        requires_admin=False,
        expected_effects="None",
        timeout_seconds=5.0,
        action_fn=lambda **kw: CommandResult(args=["cmd"], exit_code=0, stdout="Everything fine"),
        verify_fn=lambda **kw: (False, "Diagnostic check still fails (DNS resolution timed out)", []),
    )

    result = execute_repair(deceptive_repair, auto_approve=True)
    assert result.status == RepairStatus.VERIFICATION_FAILED
    assert result.verified is False
    assert "independent verification failed" in result.message


def test_repair_tuple_action_unwrapping() -> None:
    """Verify that if action_fn returns a tuple (CommandResult, data), it is safely unwrapped."""
    cmd_res = CommandResult(args=["powershell"], exit_code=0, stdout="Done")
    tuple_repair = RepairAction(
        repair_id="test.tuple",
        name="Tuple Action",
        description="Returns tuple",
        target_cause_id="TEST_CAUSE",
        risk_level=RiskLevel.LOW,
        requires_admin=False,
        expected_effects="None",
        timeout_seconds=5.0,
        action_fn=lambda **kw: (cmd_res, ["some_data"]),
        verify_fn=lambda **kw: (True, "Verified", []),
    )

    result = execute_repair(tuple_repair, auto_approve=True)
    assert result.status == RepairStatus.SUCCESS
    assert result.verified is True


def test_driver_enable_repair_action() -> None:
    """Verify drv.enable_device action returns CommandResult directly without tuple error."""
    rep = registry.get("drv.enable_device")
    assert rep is not None
    cmd_res = CommandResult(args=["powershell"], exit_code=0, stdout="Device Enabled")
    with patch("windoc.repairs.registry.run_powershell", return_value=(cmd_res, [])):
        res = rep.action_fn()
        assert isinstance(res, CommandResult)
        assert res.exit_code == 0

