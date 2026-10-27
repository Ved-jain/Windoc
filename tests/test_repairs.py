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


def test_sfc_scan_action_timeout() -> None:
    """Verify _run_sfc_scan_action uses configured timeout (defaulting to 600s)."""
    from windoc.repairs.registry import _run_sfc_scan_action
    
    mock_res = CommandResult(args=["sfc.exe", "/scannow"], exit_code=0, stdout="Clean")
    with patch("windoc.repairs.registry.run_command", return_value=mock_res) as mock_run:
        res = _run_sfc_scan_action()
        assert res.exit_code == 0
        mock_run.assert_called_once_with(["sfc.exe", "/scannow"], timeout_seconds=600.0)

    with patch("windoc.repairs.registry.run_command", return_value=mock_res) as mock_run_custom:
        res = _run_sfc_scan_action(timeout_seconds=450.0)
        assert res.exit_code == 0
        mock_run_custom.assert_called_once_with(["sfc.exe", "/scannow"], timeout_seconds=450.0)


def test_sfc_scan_verify_with_existing_dumps() -> None:
    """Verify SFC verification succeeds and does not fail merely due to pre-existing crash dumps."""
    from windoc.repairs.registry import _run_sfc_scan_verify, _run_sfc_scan_pre_state

    # 2 existing minidumps in last 7 days
    existing_dump_result = DiagnosticResult(
        check_id="sys.crash.dumps",
        domain="system",
        observation="Detected 2 recent system crash minidump(s) within the last 7 days.",
        status=CheckStatus.WARNING,
        data_source="C:\\Windows\\Minidump",
        measured_value={"crash_count": 2},
    )

    with patch("windoc.repairs.registry.check_crash_dumps", return_value=existing_dump_result):
        pre_state = _run_sfc_scan_pre_state()
        assert pre_state["baseline_crash_count"] == 2

        verified, msg, results = _run_sfc_scan_verify(pre_state=pre_state)
        assert verified is True
        assert "integrity verified" in msg
        # Dedicated SFC integrity result present with PASS status
        sfc_res = next(r for r in results if r.check_id == "sys.sfc.integrity")
        assert sfc_res.status == CheckStatus.PASS


def test_sfc_scan_verify_fails_on_new_dumps() -> None:
    """Verify SFC verification fails if a new crash dump occurred during/after repair."""
    from windoc.repairs.registry import _run_sfc_scan_verify

    new_dump_result = DiagnosticResult(
        check_id="sys.crash.dumps",
        domain="system",
        observation="Detected 3 recent system crash minidump(s).",
        status=CheckStatus.WARNING,
        data_source="C:\\Windows\\Minidump",
        measured_value={"crash_count": 3},
    )

    with patch("windoc.repairs.registry.check_crash_dumps", return_value=new_dump_result):
        # Baseline was 2, now 3
        verified, msg, results = _run_sfc_scan_verify(pre_state={"baseline_crash_count": 2})
        assert verified is False
        assert "New crash dump detected" in msg


def test_custom_action_without_kwargs() -> None:
    """Verify custom RepairAction callables without timeout_seconds or kwargs don't raise TypeError."""
    def zero_arg_action() -> CommandResult:
        return CommandResult(args=["custom"], exit_code=0, stdout="OK")

    custom_action = RepairAction(
        repair_id="custom.action",
        name="Custom Action",
        description="Testing zero-arg action callable",
        target_cause_id="TEST_CAUSE",
        risk_level=RiskLevel.LOW,
        requires_admin=False,
        expected_effects="None",
        timeout_seconds=5.0,
        action_fn=zero_arg_action,
        verify_fn=lambda **kw: (True, "Verified", []),
    )
    result = execute_repair(custom_action, auto_approve=True)
    assert result.status == RepairStatus.SUCCESS
    assert result.verified is True


def test_all_domain_actionable_causes_have_repairs() -> None:
    """Verify that every single actionable problem/cause identified across all 6 domains has a registered repair."""
    actionable_causes = [
        # Network
        "NET_PHYSICAL_DISCONNECTED",
        "NET_DHCP_LEASE_FAILED",
        "NET_GATEWAY_UNREACHABLE",
        "NET_DNS_RESOLUTION_FAILED",
        "NET_CAPTIVE_PORTAL_OR_PROXY",
        # Bluetooth
        "BTH_SERVICE_STOPPED",
        "BTH_ADAPTER_MISSING",
        "BTH_ADAPTER_DISABLED",
        "BTH_DRIVER_DEVICE_ERROR",
        "BTH_PERIPHERAL_ERROR",
        # Drivers
        "DRV_MISSING_DRIVERS",
        "DRV_DEVICE_CRASHED_CODE_43",
        "DRV_DEVICE_DISABLED_CODE_22",
        "DRV_REBOOT_REQUIRED_CODE_14",
        # Update
        "UPD_SERVICES_DISABLED",
        "UPD_REBOOT_REQUIRED",
        # System
        "SYS_CORE_SERVICES_STOPPED",
        "SYS_COMPONENT_STORE_CORRUPT",
        "SYS_RECENT_CRASHES",
        "SYS_SAFE_MODE_ACTIVE",
        # Performance
        "PERF_DISK_LOW_SPACE",
        "PERF_MEMORY_EXHAUSTION",
        "PERF_CPU_SATURATION",
        "PERF_HIGH_UPTIME_DEGRADATION",
    ]

    missing = []
    for cause in actionable_causes:
        matching = registry.find_for_cause(cause)
        if not matching:
            missing.append(cause)

    assert not missing, f"Found actionable causes without registered repairs: {missing}"


def test_reset_proxy_repair() -> None:
    """Verify net.reset_proxy execution and verification."""
    from windoc.repairs.registry import _reset_proxy_action, _reset_proxy_verify

    mock_cmd = CommandResult(args=["powershell"], exit_code=0, stdout="Proxy reset")
    with patch("windoc.repairs.registry.run_powershell", return_value=(mock_cmd, [])):
        res = _reset_proxy_action()
        assert res.exit_code == 0

    mock_conn = DiagnosticResult(
        check_id="net.connectivity.dual_probe",
        domain="network",
        observation="Internet connectivity operational",
        status=CheckStatus.PASS,
        data_source="probe",
    )
    with patch("windoc.repairs.registry.check_internet_connectivity", return_value=mock_conn):
        verified, msg, results = _reset_proxy_verify()
        assert verified is True
        assert "Proxy settings cleared" in msg


def test_bluetooth_extended_repairs() -> None:
    """Verify bth.rescan_hardware, bth.restart_device, and bth.reset_stack."""
    from windoc.repairs.registry import (
        _rescan_bth_hardware_action,
        _rescan_bth_hardware_verify,
        _restart_bth_device_action,
        _restart_bth_device_verify,
        _reset_bth_stack_action,
        _reset_bth_stack_verify,
    )

    mock_cmd = CommandResult(args=["powershell"], exit_code=0, stdout="Done")
    with patch("windoc.repairs.registry.run_powershell", return_value=(mock_cmd, [])):
        assert _rescan_bth_hardware_action().exit_code == 0
        assert _restart_bth_device_action().exit_code == 0
        assert _reset_bth_stack_action().exit_code == 0

    radio_pass = DiagnosticResult(
        check_id="bth.radio.presence",
        domain="bluetooth",
        observation="Radio present",
        status=CheckStatus.PASS,
        data_source="test",
    )
    with patch("windoc.repairs.registry.check_bluetooth_radio_adapter", return_value=radio_pass):
        verified, msg, _ = _rescan_bth_hardware_verify()
        assert verified is True

    with patch("windoc.repairs.registry.check_pnp_device_errors", return_value=[]):
        verified, msg, _ = _restart_bth_device_verify()
        assert verified is True

    svc_pass = [
        DiagnosticResult(
            check_id="bth.service.bthserv.state",
            domain="bluetooth",
            observation="Running",
            status=CheckStatus.PASS,
            data_source="test",
        )
    ]
    with patch("windoc.repairs.registry.check_bluetooth_services", return_value=svc_pass):
        verified, msg, _ = _reset_bth_stack_verify()
        assert verified is True


def test_system_exit_safe_mode_repair() -> None:
    """Verify sys.exit_safe_mode action and verification."""
    from windoc.repairs.registry import _exit_safe_mode_action, _exit_safe_mode_verify

    mock_cmd = CommandResult(args=["bcdedit.exe"], exit_code=0, stdout="The operation completed successfully.")
    with patch("windoc.repairs.registry.run_command", return_value=mock_cmd):
        res = _exit_safe_mode_action()
        assert res.exit_code == 0

    boot_pass = DiagnosticResult(
        check_id="sys.boot.state",
        domain="system",
        observation="Windows bootup state verified normal (Normal boot).",
        status=CheckStatus.PASS,
        data_source="Win32_ComputerSystem",
    )
    with patch("windoc.repairs.registry.check_os_boot_state", return_value=boot_pass):
        verified, msg, _ = _exit_safe_mode_verify()
        assert verified is True
        assert "Safe mode flag cleared" in msg


def test_update_restart_and_cache_repairs() -> None:
    """Verify upd.schedule_restart and upd.reset_cache."""
    from windoc.repairs.registry import (
        _upd_schedule_restart_action,
        _upd_schedule_restart_verify,
        _reset_update_cache_action,
        _reset_update_cache_verify,
    )

    mock_cmd = CommandResult(args=["powershell"], exit_code=0, stdout="Done")
    with patch("windoc.repairs.registry.run_powershell", return_value=(mock_cmd, [])):
        assert _upd_schedule_restart_action().exit_code == 0
        assert _reset_update_cache_action().exit_code == 0

    reboot_pass = DiagnosticResult(
        check_id="upd.system.reboot_pending",
        domain="update",
        observation="No pending restart",
        status=CheckStatus.PASS,
        data_source="registry",
    )
    with patch("windoc.repairs.registry.check_reboot_pending", return_value=reboot_pass):
        verified, msg, _ = _upd_schedule_restart_verify()
        assert verified is True

    svc_pass = [
        DiagnosticResult(
            check_id="upd.service.status",
            domain="update",
            observation="Services running",
            status=CheckStatus.PASS,
            data_source="Get-Service",
        )
    ]
    with patch("windoc.repairs.registry.check_update_services", return_value=svc_pass):
        verified, msg, _ = _reset_update_cache_verify()
        assert verified is True



