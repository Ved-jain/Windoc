"""Unit tests for Windows Performance and resource diagnostic checks, hypotheses, and repairs."""

from unittest.mock import patch

from windoc.core.engine import HypothesisStatus, evaluate_performance_hypotheses
from windoc.core.models import CheckStatus, DiagnosticResult
from windoc.core.runner import CommandResult
from windoc.domains.performance import run_all_performance_checks
from windoc.domains.performance.checks import (
    check_cpu_utilization,
    check_disk_space,
    check_memory_pressure,
    check_system_uptime,
)
from windoc.repairs.registry import (
    _clean_temp_files_action,
    _clean_temp_files_verify,
    _empty_recycle_bin_action,
    _empty_recycle_bin_verify,
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


def test_check_cpu_utilization_normal() -> None:
    """Verify CPU check passes under normal load."""
    mock_res = _make_cmd(exit_code=0, stdout="25.4")
    with patch("windoc.domains.performance.checks.run_powershell", return_value=(mock_res, None)):
        res = check_cpu_utilization()
        assert res.status == CheckStatus.PASS
        assert "within normal operating limits" in res.observation


def test_check_cpu_utilization_high() -> None:
    """Verify CPU check reports WARNING under 90%+ sustained load."""
    mock_res = _make_cmd(exit_code=0, stdout="94.2")
    with patch("windoc.domains.performance.checks.run_powershell", return_value=(mock_res, None)):
        res = check_cpu_utilization()
        assert res.status == CheckStatus.WARNING
        assert "High CPU utilization detected" in res.observation


def test_check_memory_pressure_normal() -> None:
    """Verify memory check passes when RAM usage is comfortable."""
    mock_data = {"TotalKB": 16000000, "FreeKB": 8000000}
    mock_res = _make_cmd(exit_code=0)
    with patch("windoc.domains.performance.checks.run_powershell", return_value=(mock_res, mock_data)):
        res = check_memory_pressure()
        assert res.status == CheckStatus.PASS
        assert "Physical RAM capacity is healthy" in res.observation


def test_check_memory_pressure_high() -> None:
    """Verify memory check reports WARNING when RAM usage exceeds 92%."""
    mock_data = {"TotalKB": 16000000, "FreeKB": 800000}
    mock_res = _make_cmd(exit_code=0)
    with patch("windoc.domains.performance.checks.run_powershell", return_value=(mock_res, mock_data)):
        res = check_memory_pressure()
        assert res.status == CheckStatus.WARNING
        assert "Severe memory exhaustion" in res.observation


def test_check_disk_space_healthy() -> None:
    """Verify disk space check passes when system volume C: has ample storage."""
    mock_data = {"TotalBytes": 500 * (1024**3), "FreeBytes": 150 * (1024**3)}
    mock_res = _make_cmd(exit_code=0)
    with patch("windoc.domains.performance.checks.run_powershell", return_value=(mock_res, mock_data)):
        res = check_disk_space()
        assert res.status == CheckStatus.PASS
        assert "System drive C: storage is healthy" in res.observation


def test_check_disk_space_low() -> None:
    """Verify disk space check reports WARNING when free storage is critically low."""
    mock_data = {"TotalBytes": 500 * (1024**3), "FreeBytes": 4 * (1024**3)}
    mock_res = _make_cmd(exit_code=0)
    with patch("windoc.domains.performance.checks.run_powershell", return_value=(mock_res, mock_data)):
        res = check_disk_space()
        assert res.status == CheckStatus.WARNING
        assert "Low disk space on system drive C:" in res.observation


def test_check_system_uptime_normal() -> None:
    """Verify uptime check passes when operating uptime is recent."""
    mock_res = _make_cmd(exit_code=0, stdout="48.0")
    with patch("windoc.domains.performance.checks.run_powershell", return_value=(mock_res, None)):
        res = check_system_uptime()
        assert res.status == CheckStatus.PASS
        assert "System uptime is normal" in res.observation


def test_check_system_uptime_extended() -> None:
    """Verify uptime check warns when continuous uptime exceeds 30 days."""
    mock_res = _make_cmd(exit_code=0, stdout="800.0")
    with patch("windoc.domains.performance.checks.run_powershell", return_value=(mock_res, None)):
        res = check_system_uptime()
        assert res.status == CheckStatus.WARNING
        assert "Extended system uptime" in res.observation


def test_run_all_performance_checks_aggregates() -> None:
    """Verify all 4 performance checks run in run_all_performance_checks."""
    mock_cpu = DiagnosticResult(check_id="perf.cpu.utilization", domain="performance", observation="ok", status=CheckStatus.PASS, data_source="c")
    mock_ram = DiagnosticResult(check_id="perf.memory.pressure", domain="performance", observation="ok", status=CheckStatus.PASS, data_source="r")
    mock_dsk = DiagnosticResult(check_id="perf.disk.space", domain="performance", observation="ok", status=CheckStatus.PASS, data_source="d")
    mock_upt = DiagnosticResult(check_id="perf.system.uptime", domain="performance", observation="ok", status=CheckStatus.PASS, data_source="u")

    with patch("windoc.domains.performance.checks.check_cpu_utilization", return_value=mock_cpu), \
         patch("windoc.domains.performance.checks.check_memory_pressure", return_value=mock_ram), \
         patch("windoc.domains.performance.checks.check_disk_space", return_value=mock_dsk), \
         patch("windoc.domains.performance.checks.check_system_uptime", return_value=mock_upt):
        results = run_all_performance_checks()
        assert len(results) == 4
        assert [r.check_id for r in results] == [
            "perf.cpu.utilization",
            "perf.memory.pressure",
            "perf.disk.space",
            "perf.system.uptime",
        ]


def test_evaluate_performance_healthy() -> None:
    """Verify hypothesis engine evaluates PERF_ALL_HEALTHY when all resources are green."""
    evidence = [
        DiagnosticResult(check_id="perf.cpu.utilization", domain="performance", observation="CPU load normal", status=CheckStatus.PASS, data_source="c"),
        DiagnosticResult(check_id="perf.memory.pressure", domain="performance", observation="RAM healthy", status=CheckStatus.PASS, data_source="r"),
        DiagnosticResult(check_id="perf.disk.space", domain="performance", observation="Disk space healthy", status=CheckStatus.PASS, data_source="d"),
        DiagnosticResult(check_id="perf.system.uptime", domain="performance", observation="Uptime normal", status=CheckStatus.PASS, data_source="u"),
    ]
    report = evaluate_performance_hypotheses(evidence)
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "PERF_ALL_HEALTHY"
    assert report.primary_finding.status == HypothesisStatus.CONFIRMED


def test_evaluate_performance_cpu_saturation() -> None:
    """Verify hypothesis engine isolates PERF_CPU_SATURATION when CPU is throttled."""
    evidence = [
        DiagnosticResult(check_id="perf.cpu.utilization", domain="performance", observation="High CPU utilization: 96%", status=CheckStatus.WARNING, data_source="c"),
        DiagnosticResult(check_id="perf.memory.pressure", domain="performance", observation="RAM healthy", status=CheckStatus.PASS, data_source="r"),
        DiagnosticResult(check_id="perf.disk.space", domain="performance", observation="Disk space healthy", status=CheckStatus.PASS, data_source="d"),
    ]
    report = evaluate_performance_hypotheses(evidence)
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "PERF_CPU_SATURATION"
    assert report.primary_finding.status == HypothesisStatus.CONFIRMED


def test_evaluate_performance_memory_exhaustion() -> None:
    """Verify hypothesis engine isolates PERF_MEMORY_EXHAUSTION when RAM is full."""
    evidence = [
        DiagnosticResult(check_id="perf.cpu.utilization", domain="performance", observation="CPU load normal", status=CheckStatus.PASS, data_source="c"),
        DiagnosticResult(check_id="perf.memory.pressure", domain="performance", observation="Severe memory exhaustion: 96% RAM", status=CheckStatus.WARNING, data_source="r"),
        DiagnosticResult(check_id="perf.disk.space", domain="performance", observation="Disk space healthy", status=CheckStatus.PASS, data_source="d"),
    ]
    report = evaluate_performance_hypotheses(evidence)
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "PERF_MEMORY_EXHAUSTION"
    assert report.primary_finding.status == HypothesisStatus.CONFIRMED


def test_evaluate_performance_disk_low() -> None:
    """Verify hypothesis engine isolates PERF_DISK_LOW_SPACE when drive C: is low on space."""
    evidence = [
        DiagnosticResult(check_id="perf.cpu.utilization", domain="performance", observation="CPU load normal", status=CheckStatus.PASS, data_source="c"),
        DiagnosticResult(check_id="perf.memory.pressure", domain="performance", observation="RAM healthy", status=CheckStatus.PASS, data_source="r"),
        DiagnosticResult(check_id="perf.disk.space", domain="performance", observation="Low disk space on C: 4GB free", status=CheckStatus.WARNING, data_source="d"),
    ]
    report = evaluate_performance_hypotheses(evidence)
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "PERF_DISK_LOW_SPACE"
    assert report.primary_finding.status == HypothesisStatus.CONFIRMED


def test_clean_temp_files_action_and_verify() -> None:
    """Verify temporary files cleaning repair action and verify functions."""
    mock_cmd = _make_cmd(exit_code=0)
    with patch("windoc.repairs.registry.run_powershell", return_value=(mock_cmd, None)):
        res = _clean_temp_files_action()
        assert res.is_success

    pass_disk = DiagnosticResult(check_id="perf.disk.space", domain="performance", observation="Disk healthy", status=CheckStatus.PASS, data_source="d")
    with patch("windoc.repairs.registry.check_disk_space", return_value=pass_disk):
        success, msg, _ = _clean_temp_files_verify()
        assert success
        assert "cleared" in msg


def test_empty_recycle_bin_action_and_verify() -> None:
    """Verify Recycle Bin purging repair action and verify functions."""
    mock_cmd = _make_cmd(exit_code=0)
    with patch("windoc.repairs.registry.run_powershell", return_value=(mock_cmd, None)):
        res = _empty_recycle_bin_action()
        assert res.is_success

    pass_disk = DiagnosticResult(check_id="perf.disk.space", domain="performance", observation="Disk healthy", status=CheckStatus.PASS, data_source="d")
    with patch("windoc.repairs.registry.check_disk_space", return_value=pass_disk):
        success, msg, _ = _empty_recycle_bin_verify()
        assert success
        assert "purged" in msg
