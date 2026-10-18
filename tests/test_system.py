"""Unit tests for Windows System integrity diagnostic checks, hypotheses, and repairs."""

from unittest.mock import patch

from windoc.core.engine import HypothesisStatus, evaluate_system_hypotheses
from windoc.core.models import CheckStatus, DiagnosticResult
from windoc.core.runner import CommandResult
from windoc.domains.system import run_all_system_checks
from windoc.domains.system.checks import (
    check_component_store_health,
    check_core_system_services,
    check_crash_dumps,
    check_os_boot_state,
)
from windoc.repairs.registry import (
    _repair_component_store_action,
    _repair_component_store_verify,
    _restart_system_services_action,
    _restart_system_services_verify,
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


def test_check_core_services_all_running() -> None:
    """Verify check passes when all 5 core subsystem services are Running."""
    mock_svcs = [
        {"Name": "RpcSs", "DisplayName": "RPC", "Status": 4, "StartType": 2},
        {"Name": "DcomLaunch", "DisplayName": "DCOM", "Status": 4, "StartType": 2},
        {"Name": "EventLog", "DisplayName": "EventLog", "Status": 4, "StartType": 2},
        {"Name": "PlugPlay", "DisplayName": "PlugPlay", "Status": 4, "StartType": 3},
        {"Name": "Winmgmt", "DisplayName": "WMI", "Status": 4, "StartType": 2},
    ]
    mock_res = _make_cmd(exit_code=0)

    with patch("windoc.domains.system.checks.run_powershell", return_value=(mock_res, mock_svcs)):
        results = check_core_system_services()
        assert len(results) == 1
        assert results[0].status == CheckStatus.PASS
        assert "operational" in results[0].observation


def test_check_core_services_stopped() -> None:
    """Verify check reports FAIL when a core subsystem service is stopped."""
    mock_svcs = [
        {"Name": "RpcSs", "DisplayName": "RPC", "Status": 4, "StartType": 2},
        {"Name": "Winmgmt", "DisplayName": "WMI", "Status": 1, "StartType": 2},
    ]
    mock_res = _make_cmd(exit_code=0)

    with patch("windoc.domains.system.checks.run_powershell", return_value=(mock_res, mock_svcs)):
        results = check_core_system_services()
        assert len(results) == 1
        assert results[0].status == CheckStatus.FAIL
        assert results[0].check_id == "sys.service.stopped"
        assert "WMI (Winmgmt)" in results[0].observation


def test_check_component_store_elevated_clean() -> None:
    """Verify DISM CheckHealth passes when no corruption detected."""
    mock_dism = _make_cmd(exit_code=0, stdout="No component store corruption detected.\nThe operation completed successfully.")
    with patch("windoc.domains.system.checks.run_command", return_value=mock_dism):
        res = check_component_store_health()
        assert res.status == CheckStatus.PASS
        assert "verified healthy" in res.observation


def test_check_component_store_elevated_corrupted() -> None:
    """Verify DISM CheckHealth reports corruption when image is repairable."""
    mock_dism = _make_cmd(exit_code=0, stdout="The component store is repairable.\nThe operation completed successfully.")
    with patch("windoc.domains.system.checks.run_command", return_value=mock_dism):
        res = check_component_store_health()
        assert res.status == CheckStatus.FAIL
        assert res.check_id == "sys.dism.corrupted"
        assert "corruption detected" in res.observation


def test_check_component_store_fallback_non_elevated() -> None:
    """Verify fallback to CBS registry / logs when DISM requires elevation (code 740)."""
    mock_dism = _make_cmd(exit_code=1, stderr="Error: 740 Elevated permissions required")
    mock_cbs_data = {"CBS_Exists": True, "CBS_Reg": True}
    mock_cbs_res = _make_cmd(exit_code=0)

    with patch("windoc.domains.system.checks.run_command", return_value=mock_dism), \
         patch("windoc.domains.system.checks.run_powershell", return_value=(mock_cbs_res, mock_cbs_data)):
        res = check_component_store_health()
        assert res.status == CheckStatus.PASS
        assert "intact" in res.observation


def test_check_crash_dumps_none() -> None:
    """Verify crash dumps check passes when no recent dumps exist."""
    mock_res = _make_cmd(exit_code=0)
    mock_data = {"HasCrashDumps": False, "Count": 0}

    with patch("windoc.domains.system.checks.run_powershell", return_value=(mock_res, mock_data)):
        res = check_crash_dumps()
        assert res.status == CheckStatus.PASS
        assert "No recent system crash" in res.observation


def test_check_crash_dumps_detected() -> None:
    """Verify crash dumps check reports warning when minidump found."""
    mock_res = _make_cmd(exit_code=0)
    mock_data = {"HasCrashDumps": True, "Count": 2}

    with patch("windoc.domains.system.checks.run_powershell", return_value=(mock_res, mock_data)):
        res = check_crash_dumps()
        assert res.status == CheckStatus.WARNING
        assert "2 recent system crash minidump(s)" in res.observation


def test_check_os_boot_state_normal() -> None:
    """Verify boot state check passes on normal boot."""
    mock_res = _make_cmd(exit_code=0, stdout="Normal boot")
    with patch("windoc.domains.system.checks.run_powershell", return_value=(mock_res, None)):
        res = check_os_boot_state()
        assert res.status == CheckStatus.PASS
        assert "Normal boot" in res.observation


def test_check_os_boot_state_safe_mode() -> None:
    """Verify boot state check warns on safe mode boot."""
    mock_res = _make_cmd(exit_code=0, stdout="Safe mode with networking")
    with patch("windoc.domains.system.checks.run_powershell", return_value=(mock_res, None)):
        res = check_os_boot_state()
        assert res.status == CheckStatus.WARNING
        assert "Safe/Diagnostic mode" in res.observation


def test_run_all_system_checks_aggregates() -> None:
    """Verify all 4 system checks run in run_all_system_checks."""
    mock_svc = DiagnosticResult(check_id="sys.service.status", domain="system", observation="ok", status=CheckStatus.PASS, data_source="s")
    mock_dism = DiagnosticResult(check_id="sys.dism.health", domain="system", observation="ok", status=CheckStatus.PASS, data_source="d")
    mock_crash = DiagnosticResult(check_id="sys.crash.dumps", domain="system", observation="ok", status=CheckStatus.PASS, data_source="c")
    mock_boot = DiagnosticResult(check_id="sys.boot.state", domain="system", observation="ok", status=CheckStatus.PASS, data_source="b")

    with patch("windoc.domains.system.checks.check_core_system_services", return_value=[mock_svc]), \
         patch("windoc.domains.system.checks.check_component_store_health", return_value=mock_dism), \
         patch("windoc.domains.system.checks.check_crash_dumps", return_value=mock_crash), \
         patch("windoc.domains.system.checks.check_os_boot_state", return_value=mock_boot):
        results = run_all_system_checks()
        assert len(results) == 4
        assert [r.check_id for r in results] == [
            "sys.service.status",
            "sys.dism.health",
            "sys.crash.dumps",
            "sys.boot.state",
        ]


def test_evaluate_system_healthy() -> None:
    """Verify hypothesis engine isolates SYS_ALL_HEALTHY when all system checks pass."""
    evidence = [
        DiagnosticResult(check_id="sys.service.status", domain="system", observation="Services operational", status=CheckStatus.PASS, data_source="s"),
        DiagnosticResult(check_id="sys.dism.health", domain="system", observation="Component store healthy", status=CheckStatus.PASS, data_source="d"),
        DiagnosticResult(check_id="sys.crash.dumps", domain="system", observation="No crashes", status=CheckStatus.PASS, data_source="c"),
        DiagnosticResult(check_id="sys.boot.state", domain="system", observation="Normal boot", status=CheckStatus.PASS, data_source="b"),
    ]
    report = evaluate_system_hypotheses(evidence)
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "SYS_ALL_HEALTHY"
    assert report.primary_finding.status == HypothesisStatus.CONFIRMED


def test_evaluate_system_core_services_stopped() -> None:
    """Verify hypothesis engine isolates SYS_CORE_SERVICES_STOPPED when services inactive."""
    evidence = [
        DiagnosticResult(check_id="sys.service.stopped", domain="system", observation="Winmgmt stopped", status=CheckStatus.FAIL, data_source="s"),
        DiagnosticResult(check_id="sys.dism.health", domain="system", observation="Component store healthy", status=CheckStatus.PASS, data_source="d"),
    ]
    report = evaluate_system_hypotheses(evidence)
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "SYS_CORE_SERVICES_STOPPED"
    assert report.primary_finding.status == HypothesisStatus.CONFIRMED


def test_evaluate_system_component_store_corrupted() -> None:
    """Verify hypothesis engine isolates SYS_COMPONENT_STORE_CORRUPT when DISM detects corruption."""
    evidence = [
        DiagnosticResult(check_id="sys.service.status", domain="system", observation="Services operational", status=CheckStatus.PASS, data_source="s"),
        DiagnosticResult(check_id="sys.dism.corrupted", domain="system", observation="Component store corrupt", status=CheckStatus.FAIL, data_source="d"),
    ]
    report = evaluate_system_hypotheses(evidence)
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "SYS_COMPONENT_STORE_CORRUPT"
    assert report.primary_finding.status == HypothesisStatus.CONFIRMED


def test_repair_component_store_action_and_verify() -> None:
    """Verify DISM RestoreHealth action and verification."""
    mock_cmd = _make_cmd(exit_code=0)
    with patch("windoc.repairs.registry.run_command", return_value=mock_cmd):
        res = _repair_component_store_action()
        assert res.is_success

    pass_dism = DiagnosticResult(check_id="sys.dism.health", domain="system", observation="healthy", status=CheckStatus.PASS, data_source="d")
    with patch("windoc.repairs.registry.check_component_store_health", return_value=pass_dism):
        success, msg, _ = _repair_component_store_verify()
        assert success
        assert "restored" in msg


def test_restart_system_services_action_and_verify() -> None:
    """Verify core services restart action and verification."""
    mock_cmd = _make_cmd(exit_code=0)
    with patch("windoc.repairs.registry.run_powershell", return_value=(mock_cmd, None)):
        res = _restart_system_services_action()
        assert res.is_success

    pass_svc = DiagnosticResult(check_id="sys.service.status", domain="system", observation="ok", status=CheckStatus.PASS, data_source="s")
    with patch("windoc.repairs.registry.check_core_system_services", return_value=[pass_svc]):
        success, msg, _ = _restart_system_services_verify()
        assert success
        assert "active and running" in msg
