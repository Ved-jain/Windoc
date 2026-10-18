"""Unit tests for Windows Update diagnostic checks, hypothesis evaluation, and repairs."""

from unittest.mock import patch

from windoc.core.engine import HypothesisStatus, evaluate_update_hypotheses
from windoc.core.models import CheckStatus, DiagnosticResult
from windoc.core.runner import CommandResult
from windoc.domains.update import run_all_update_checks
from windoc.domains.update.checks import (
    check_download_cache,
    check_recent_hotfixes,
    check_reboot_pending,
    check_update_services,
)
from windoc.repairs.registry import _reset_update_services_action, _reset_update_services_verify


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


def test_check_update_services_running() -> None:
    """Verify services check passes when services are properly configured."""
    mock_svcs = [
        {"Name": "wuauserv", "DisplayName": "Windows Update", "Status": 1, "StartType": 3},
        {"Name": "bits", "DisplayName": "Background Intelligent Transfer Service", "Status": 4, "StartType": 2},
        {"Name": "cryptsvc", "DisplayName": "Cryptographic Services", "Status": 4, "StartType": 2},
        {"Name": "TrustedInstaller", "DisplayName": "Windows Modules Installer", "Status": 1, "StartType": 3},
    ]
    mock_res = _make_cmd(exit_code=0)

    with patch("windoc.domains.update.checks.run_powershell", return_value=(mock_res, mock_svcs)):
        results = check_update_services()
        assert len(results) == 1
        assert results[0].status == CheckStatus.PASS
        assert "configured properly" in results[0].observation


def test_check_update_services_disabled() -> None:
    """Verify services check reports FAIL when a critical service is disabled."""
    mock_svcs = [
        {"Name": "wuauserv", "DisplayName": "Windows Update", "Status": 1, "StartType": 4},
        {"Name": "bits", "DisplayName": "Background Intelligent Transfer Service", "Status": 4, "StartType": 2},
    ]
    mock_res = _make_cmd(exit_code=0)

    with patch("windoc.domains.update.checks.run_powershell", return_value=(mock_res, mock_svcs)):
        results = check_update_services()
        assert len(results) == 1
        assert results[0].status == CheckStatus.FAIL
        assert results[0].check_id == "upd.service.disabled"
        assert "Windows Update (wuauserv)" in results[0].observation


def test_check_update_services_query_error() -> None:
    """Verify error status returned on query failure."""
    mock_res = _make_cmd(exit_code=1, stderr="Access denied")

    with patch("windoc.domains.update.checks.run_powershell", return_value=(mock_res, None)):
        results = check_update_services()
        assert len(results) == 1
        assert results[0].status == CheckStatus.ERROR


def test_check_reboot_pending_yes() -> None:
    """Verify reboot pending detection."""
    mock_data = {"WU_Reboot": True, "CBS_Reboot": False}
    mock_res = _make_cmd(exit_code=0)

    with patch("windoc.domains.update.checks.run_powershell", return_value=(mock_res, mock_data)):
        res = check_reboot_pending()
        assert res.status == CheckStatus.WARNING
        assert "System restart required" in res.observation


def test_check_reboot_pending_no() -> None:
    """Verify reboot check passes when no restart pending."""
    mock_data = {"WU_Reboot": False, "CBS_Reboot": False}
    mock_res = _make_cmd(exit_code=0)

    with patch("windoc.domains.update.checks.run_powershell", return_value=(mock_res, mock_data)):
        res = check_reboot_pending()
        assert res.status == CheckStatus.PASS
        assert "No pending system restarts" in res.observation


def test_check_recent_hotfixes_found() -> None:
    """Verify hotfixes query returns recent KB list."""
    mock_hotfixes = [
        {"HotFixID": "KB5044284", "Description": "Security Update"},
        {"HotFixID": "KB5043076", "Description": "Update"},
    ]
    mock_res = _make_cmd(exit_code=0)

    with patch("windoc.domains.update.checks.run_powershell", return_value=(mock_res, mock_hotfixes)):
        res = check_recent_hotfixes()
        assert res.status == CheckStatus.PASS
        assert "KB5044284" in res.observation


def test_check_recent_hotfixes_empty() -> None:
    """Verify warning returned when hotfix list is empty."""
    mock_res = _make_cmd(exit_code=0)

    with patch("windoc.domains.update.checks.run_powershell", return_value=(mock_res, [])):
        res = check_recent_hotfixes()
        assert res.status == CheckStatus.WARNING


def test_check_download_cache_exists() -> None:
    """Verify SoftwareDistribution cache verification."""
    mock_res = _make_cmd(exit_code=0)

    with patch("windoc.domains.update.checks.run_powershell", return_value=(mock_res, True)):
        res = check_download_cache()
        assert res.status == CheckStatus.PASS
        assert "intact" in res.observation


def test_check_download_cache_missing() -> None:
    """Verify warning when download cache is missing."""
    mock_res = _make_cmd(exit_code=0)

    with patch("windoc.domains.update.checks.run_powershell", return_value=(mock_res, False)):
        res = check_download_cache()
        assert res.status == CheckStatus.WARNING


def test_run_all_update_checks_aggregates() -> None:
    """Verify all 4 update checks are executed in run_all_update_checks."""
    mock_svc = DiagnosticResult(check_id="upd.service.status", domain="update", observation="ok", status=CheckStatus.PASS, data_source="s")
    mock_reb = DiagnosticResult(check_id="upd.system.reboot_pending", domain="update", observation="ok", status=CheckStatus.PASS, data_source="r")
    mock_hot = DiagnosticResult(check_id="upd.history.hotfixes", domain="update", observation="ok", status=CheckStatus.PASS, data_source="h")
    mock_cac = DiagnosticResult(check_id="upd.cache.integrity", domain="update", observation="ok", status=CheckStatus.PASS, data_source="c")

    with patch("windoc.domains.update.checks.check_update_services", return_value=[mock_svc]), \
         patch("windoc.domains.update.checks.check_reboot_pending", return_value=mock_reb), \
         patch("windoc.domains.update.checks.check_recent_hotfixes", return_value=mock_hot), \
         patch("windoc.domains.update.checks.check_download_cache", return_value=mock_cac):
        results = run_all_update_checks()
        assert len(results) == 4
        assert [r.check_id for r in results] == [
            "upd.service.status",
            "upd.system.reboot_pending",
            "upd.history.hotfixes",
            "upd.cache.integrity",
        ]


def test_evaluate_update_healthy() -> None:
    """Verify update hypothesis engine evaluates UPD_ALL_HEALTHY when all checks pass."""
    evidence = [
        DiagnosticResult(check_id="upd.service.status", domain="update", observation="Services configured", status=CheckStatus.PASS, data_source="s"),
        DiagnosticResult(check_id="upd.system.reboot_pending", domain="update", observation="No reboot pending", status=CheckStatus.PASS, data_source="r"),
        DiagnosticResult(check_id="upd.history.hotfixes", domain="update", observation="Hotfixes found", status=CheckStatus.PASS, data_source="h"),
    ]
    report = evaluate_update_hypotheses(evidence)
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "UPD_ALL_HEALTHY"
    assert report.primary_finding.status == HypothesisStatus.CONFIRMED


def test_evaluate_update_services_disabled() -> None:
    """Verify update hypothesis engine isolates UPD_SERVICES_DISABLED when services are disabled."""
    evidence = [
        DiagnosticResult(check_id="upd.service.disabled", domain="update", observation="wuauserv disabled", status=CheckStatus.FAIL, data_source="s"),
        DiagnosticResult(check_id="upd.system.reboot_pending", domain="update", observation="No reboot pending", status=CheckStatus.PASS, data_source="r"),
    ]
    report = evaluate_update_hypotheses(evidence)
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "UPD_SERVICES_DISABLED"
    assert report.primary_finding.status == HypothesisStatus.CONFIRMED


def test_evaluate_update_reboot_required() -> None:
    """Verify update hypothesis engine isolates UPD_REBOOT_REQUIRED when reboot is pending."""
    evidence = [
        DiagnosticResult(check_id="upd.service.status", domain="update", observation="Services configured", status=CheckStatus.PASS, data_source="s"),
        DiagnosticResult(check_id="upd.system.reboot_pending", domain="update", observation="System restart required", status=CheckStatus.WARNING, data_source="r"),
    ]
    report = evaluate_update_hypotheses(evidence)
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "UPD_REBOOT_REQUIRED"
    assert report.primary_finding.status == HypothesisStatus.CONFIRMED


def test_update_reset_services_repair_action() -> None:
    """Verify _reset_update_services_action invokes PowerShell correctly."""
    mock_res = _make_cmd(exit_code=0)
    with patch("windoc.repairs.registry.run_powershell", return_value=(mock_res, None)) as mock_run:
        res = _reset_update_services_action()
        assert res.is_success
        mock_run.assert_called_once()


def test_update_reset_services_repair_verify() -> None:
    """Verify _reset_update_services_verify handles pass and fail states."""
    pass_svc = DiagnosticResult(check_id="upd.service.status", domain="update", observation="ok", status=CheckStatus.PASS, data_source="s")
    fail_svc = DiagnosticResult(check_id="upd.service.disabled", domain="update", observation="bits disabled", status=CheckStatus.FAIL, data_source="s")

    with patch("windoc.repairs.registry.check_update_services", return_value=[pass_svc]):
        success, msg, _ = _reset_update_services_verify()
        assert success
        assert "restored" in msg

    with patch("windoc.repairs.registry.check_update_services", return_value=[fail_svc]):
        success, msg, _ = _reset_update_services_verify()
        assert not success
        assert "Failed to restore" in msg
