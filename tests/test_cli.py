"""Unit tests for the WinDoc CLI interface."""

import pytest
from typer.testing import CliRunner

from windoc import __version__
from windoc.cli import app

runner = CliRunner()


def test_cli_version() -> None:
    """Verify that `windoc --version` prints the version string and exits with 0."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "WinDoc" in result.stdout
    assert __version__ in result.stdout


def test_cli_help() -> None:
    """Verify that `windoc --help` displays command usage and subcommands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Evidence-driven Windows diagnostics" in result.stdout
    assert "info" in result.stdout
    assert "list-domains" in result.stdout


def test_cli_info() -> None:
    """Verify that `windoc info` runs cleanly and reports system information."""
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "WinDoc Environment" in result.stdout
    assert "Operating System" in result.stdout
    assert "Administrator Privileges" in result.stdout


def test_cli_list_domains() -> None:
    """Verify that `windoc list-domains` displays supported and planned diagnostic domains."""
    result = runner.invoke(app, ["list-domains"])
    assert result.exit_code == 0
    assert "Diagnostic Domains" in result.stdout
    assert "network" in result.stdout
    assert "bluetooth" in result.stdout
    assert "drivers" in result.stdout
    assert "update" in result.stdout


def test_cli_diagnose_network() -> None:
    """Verify `windoc diagnose network` command output formatting."""
    from unittest.mock import patch
    from windoc.core.models import CheckStatus, DiagnosticResult

    mock_result = DiagnosticResult(
        check_id="net.adapter.state",
        domain="network",
        observation="Adapter operational",
        status=CheckStatus.PASS,
        data_source="Get-NetAdapter",
    )
    with patch("windoc.cli.run_all_network_checks", return_value=[mock_result]):
        result = runner.invoke(app, ["diagnose", "network"])
        assert result.exit_code == 0
        assert "Network Diagnostic Report" in result.stdout
        assert "net.adapter.state" in result.stdout
        assert "PASS" in result.stdout


def test_cli_scan() -> None:
    """Verify `windoc scan` command triggers diagnostic scans across all active domains."""
    from unittest.mock import patch
    from windoc.core.models import CheckStatus, DiagnosticResult

    net_res = DiagnosticResult(
        check_id="net.dns.test",
        domain="network",
        observation="DNS test passed",
        status=CheckStatus.PASS,
        data_source="socket",
    )
    bth_res = DiagnosticResult(
        check_id="bth.service.bthserv.state",
        domain="bluetooth",
        observation="Service running",
        status=CheckStatus.PASS,
        data_source="Get-Service",
    )
    drv_res = DiagnosticResult(
        check_id="drv.pnp.all_healthy",
        domain="drivers",
        observation="All devices operational",
        status=CheckStatus.PASS,
        data_source="Get-PnpDevice",
    )
    upd_res = DiagnosticResult(
        check_id="upd.service.status",
        domain="update",
        observation="Update services operational",
        status=CheckStatus.PASS,
        data_source="Get-Service",
    )
    sys_res = DiagnosticResult(
        check_id="sys.service.status",
        domain="system",
        observation="System services operational",
        status=CheckStatus.PASS,
        data_source="Get-Service",
    )
    perf_res = DiagnosticResult(
        check_id="perf.cpu.utilization",
        domain="performance",
        observation="CPU load is normal",
        status=CheckStatus.PASS,
        data_source="Win32_Processor",
    )
    with patch("windoc.cli.run_all_network_checks", return_value=[net_res]), \
         patch("windoc.domains.bluetooth.run_all_bluetooth_checks", return_value=[bth_res]), \
         patch("windoc.domains.drivers.run_all_driver_checks", return_value=[drv_res]), \
         patch("windoc.domains.update.run_all_update_checks", return_value=[upd_res]), \
         patch("windoc.domains.system.run_all_system_checks", return_value=[sys_res]), \
         patch("windoc.domains.performance.run_all_performance_checks", return_value=[perf_res]):
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "Starting comprehensive diagnostic scan" in result.stdout
        assert "Network Diagnostics" in result.stdout
        assert "net.dns.test" in result.stdout
        assert "Bluetooth Diagnostics" in result.stdout
        assert "bth.service.bthserv.state" in result.stdout
        assert "Hardware & Driver Diagnostics" in result.stdout
        assert "Windows Update Diagnostics" in result.stdout
        assert "Windows System Diagnostics" in result.stdout
        assert "Performance & Resource Diagnostics" in result.stdout


def test_cli_list_repairs() -> None:
    """Verify `windoc list-repairs` displays allowlisted repair table."""
    result = runner.invoke(app, ["list-repairs"])
    assert result.exit_code == 0
    assert "Controlled Repair Registry" in result.stdout
    assert "net.flush_dns" in result.stdout
    assert "net.renew_dhcp" in result.stdout
    assert "drv.rescan_devices" in result.stdout


def test_cli_repair_cmd_success() -> None:
    """Verify `windoc repair` executes and renders success panel."""
    from unittest.mock import patch
    from windoc.repairs.models import RepairExecutionResult, RepairStatus

    mock_res = RepairExecutionResult(
        repair_id="net.flush_dns",
        name="Flush DNS Resolver Cache",
        status=RepairStatus.SUCCESS,
        message="DNS resolution verified successfully.",
        verified=True,
    )
    with patch("windoc.cli.execute_repair", return_value=mock_res):
        result = runner.invoke(app, ["repair", "net.flush_dns", "--yes"])
        assert result.exit_code == 0
        assert "Repair Verification: SUCCESS" in result.stdout
        assert "DNS resolution verified successfully" in result.stdout


def test_cli_repair_unknown_id() -> None:
    """Verify `windoc repair` with invalid ID exits with error code 1."""
    result = runner.invoke(app, ["repair", "invalid.non_existent_repair"])
    assert result.exit_code == 1
    assert "Unknown repair" in result.stdout


def test_cli_diagnose_bluetooth() -> None:
    """Verify `windoc diagnose bluetooth` command output formatting."""
    from unittest.mock import patch
    from windoc.core.models import CheckStatus, DiagnosticResult

    mock_result = DiagnosticResult(
        check_id="bth.service.bthserv.state",
        domain="bluetooth",
        observation="Service running",
        status=CheckStatus.PASS,
        data_source="Get-Service",
    )
    with patch("windoc.domains.bluetooth.run_all_bluetooth_checks", return_value=[mock_result]):
        result = runner.invoke(app, ["diagnose", "bluetooth"])
        assert result.exit_code == 0
        assert "Bluetooth Diagnostic Report" in result.stdout
        assert "bth.service.bthserv.state" in result.stdout
        assert "PASS" in result.stdout


def test_cli_diagnose_drivers() -> None:
    """Verify `windoc diagnose drivers` command output formatting."""
    from unittest.mock import patch
    from windoc.core.models import CheckStatus, DiagnosticResult

    mock_result = DiagnosticResult(
        check_id="drv.pnp.all_healthy",
        domain="drivers",
        observation="All devices operational",
        status=CheckStatus.PASS,
        data_source="Get-PnpDevice",
    )
    with patch("windoc.domains.drivers.run_all_driver_checks", return_value=[mock_result]):
        result = runner.invoke(app, ["diagnose", "drivers"])
        assert result.exit_code == 0
        assert "Hardware & Driver Diagnostic Report" in result.stdout
        assert "drv.pnp.all_healthy" in result.stdout


def test_cli_diagnose_update() -> None:
    """Verify `windoc diagnose update` command output formatting."""
    from unittest.mock import patch
    from windoc.core.models import CheckStatus, DiagnosticResult

    mock_result = DiagnosticResult(
        check_id="upd.service.status",
        domain="update",
        observation="All Windows Update services configured properly",
        status=CheckStatus.PASS,
        data_source="Get-Service",
    )
    with patch("windoc.domains.update.run_all_update_checks", return_value=[mock_result]):
        result = runner.invoke(app, ["diagnose", "update"])
        assert result.exit_code == 0
        assert "Windows Update Diagnostic Report" in result.stdout
        assert "upd.service.status" in result.stdout
        assert "PASS" in result.stdout


def test_cli_diagnose_system() -> None:
    """Verify `windoc diagnose system` command output formatting."""
    from unittest.mock import patch
    from windoc.core.models import CheckStatus, DiagnosticResult

    mock_result = DiagnosticResult(
        check_id="sys.service.status",
        domain="system",
        observation="All core Windows services operational",
        status=CheckStatus.PASS,
        data_source="Get-Service",
    )
    with patch("windoc.domains.system.run_all_system_checks", return_value=[mock_result]):
        result = runner.invoke(app, ["diagnose", "system"])
        assert result.exit_code == 0
        assert "Windows System Diagnostic Report" in result.stdout
        assert "sys.service.status" in result.stdout
        assert "PASS" in result.stdout


def test_cli_diagnose_performance() -> None:
    """Verify `windoc diagnose performance` command output formatting."""
    from unittest.mock import patch
    from windoc.core.models import CheckStatus, DiagnosticResult

    mock_result = DiagnosticResult(
        check_id="perf.cpu.utilization",
        domain="performance",
        observation="CPU load is within normal operating limits",
        status=CheckStatus.PASS,
        data_source="Win32_Processor",
    )
    with patch("windoc.domains.performance.run_all_performance_checks", return_value=[mock_result]):
        result = runner.invoke(app, ["diagnose", "performance"])
        assert result.exit_code == 0
        assert "Performance & Resource Diagnostic Report" in result.stdout
        assert "perf.cpu.utilization" in result.stdout
        assert "PASS" in result.stdout


def test_cli_activate() -> None:
    """Verify `windoc activate` registers launcher and exits with 0."""
    result = runner.invoke(app, ["activate"])
    assert result.exit_code == 0
    assert "WinDoc Activation: Ready" in result.stdout or "WinDoc is now globally active" in result.stdout


def test_cli_fix_all_healthy() -> None:
    """Verify `windoc fix` reports all healthy when no issues exist."""
    from unittest.mock import patch
    from windoc.core.engine import DiagnosisFinding, DiagnosisReport, HypothesisStatus

    healthy_verdict = DiagnosisFinding(
        cause_id="NET_ALL_HEALTHY",
        title="All Network Subsystems Operational",
        description="Healthy",
        confidence=1.0,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="None",
        supporting_evidence=[],
    )
    bth_healthy_verdict = DiagnosisFinding(
        cause_id="BTH_ALL_HEALTHY",
        title="All Bluetooth Subsystems Operational",
        description="Healthy",
        confidence=1.0,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="None",
        supporting_evidence=[],
    )
    drv_healthy_verdict = DiagnosisFinding(
        cause_id="DRV_ALL_HEALTHY",
        title="All Hardware Devices and Drivers Operational",
        description="Healthy",
        confidence=1.0,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="None",
        supporting_evidence=[],
    )
    upd_healthy_verdict = DiagnosisFinding(
        cause_id="UPD_ALL_HEALTHY",
        title="Windows Update Subsystem Operational",
        description="Healthy",
        confidence=1.0,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="None",
        supporting_evidence=[],
    )
    sys_healthy_verdict = DiagnosisFinding(
        cause_id="SYS_ALL_HEALTHY",
        title="Windows System Integrity Operational",
        description="Healthy",
        confidence=1.0,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="None",
        supporting_evidence=[],
    )
    perf_healthy_verdict = DiagnosisFinding(
        cause_id="PERF_ALL_HEALTHY",
        title="System Performance & Resources Optimal",
        description="Healthy",
        confidence=1.0,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="None",
        supporting_evidence=[],
    )
    mock_net_report = DiagnosisReport(
        domain="network",
        summary="Healthy",
        primary_finding=healthy_verdict,
        all_findings=[healthy_verdict],
    )
    mock_bth_report = DiagnosisReport(
        domain="bluetooth",
        summary="Healthy",
        primary_finding=bth_healthy_verdict,
        all_findings=[bth_healthy_verdict],
    )
    mock_drv_report = DiagnosisReport(
        domain="drivers",
        summary="Healthy",
        primary_finding=drv_healthy_verdict,
        all_findings=[drv_healthy_verdict],
    )
    mock_upd_report = DiagnosisReport(
        domain="update",
        summary="Healthy",
        primary_finding=upd_healthy_verdict,
        all_findings=[upd_healthy_verdict],
    )
    mock_sys_report = DiagnosisReport(
        domain="system",
        summary="Healthy",
        primary_finding=sys_healthy_verdict,
        all_findings=[sys_healthy_verdict],
    )
    mock_perf_report = DiagnosisReport(
        domain="performance",
        summary="Healthy",
        primary_finding=perf_healthy_verdict,
        all_findings=[perf_healthy_verdict],
    )

    with patch("windoc.cli.run_all_network_checks", return_value=[]), \
         patch("windoc.domains.bluetooth.run_all_bluetooth_checks", return_value=[]), \
         patch("windoc.domains.drivers.run_all_driver_checks", return_value=[]), \
         patch("windoc.domains.update.run_all_update_checks", return_value=[]), \
         patch("windoc.domains.system.run_all_system_checks", return_value=[]), \
         patch("windoc.domains.performance.run_all_performance_checks", return_value=[]), \
         patch("windoc.core.engine.evaluate_network_hypotheses", return_value=mock_net_report), \
         patch("windoc.core.engine.evaluate_bluetooth_hypotheses", return_value=mock_bth_report), \
         patch("windoc.core.engine.evaluate_driver_hypotheses", return_value=mock_drv_report), \
         patch("windoc.core.engine.evaluate_update_hypotheses", return_value=mock_upd_report), \
         patch("windoc.core.engine.evaluate_system_hypotheses", return_value=mock_sys_report), \
         patch("windoc.core.engine.evaluate_performance_hypotheses", return_value=mock_perf_report):
        result = runner.invoke(app, ["fix"])
        assert result.exit_code == 0
        assert "All scanned subsystems are healthy" in result.stdout


def test_cli_fix_with_detected_issue_auto_approve() -> None:
    """Verify `windoc fix --yes` executes repair when an issue is detected."""
    from unittest.mock import patch
    from windoc.core.engine import DiagnosisFinding, DiagnosisReport, HypothesisStatus
    from windoc.repairs.models import RepairExecutionResult, RepairStatus

    failing_verdict = DiagnosisFinding(
        cause_id="NET_DNS_RESOLUTION_FAILED",
        title="DNS Resolution Failure",
        description="DNS failed",
        confidence=0.9,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="Flush DNS",
        supporting_evidence=["socket failed"],
    )
    bth_healthy_verdict = DiagnosisFinding(
        cause_id="BTH_ALL_HEALTHY",
        title="All Bluetooth Subsystems Operational",
        description="Healthy",
        confidence=1.0,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="None",
        supporting_evidence=[],
    )
    drv_healthy_verdict = DiagnosisFinding(
        cause_id="DRV_ALL_HEALTHY",
        title="All Hardware Devices and Drivers Operational",
        description="Healthy",
        confidence=1.0,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="None",
        supporting_evidence=[],
    )
    upd_healthy_verdict = DiagnosisFinding(
        cause_id="UPD_ALL_HEALTHY",
        title="Windows Update Subsystem Operational",
        description="Healthy",
        confidence=1.0,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="None",
        supporting_evidence=[],
    )
    sys_healthy_verdict = DiagnosisFinding(
        cause_id="SYS_ALL_HEALTHY",
        title="Windows System Integrity Operational",
        description="Healthy",
        confidence=1.0,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="None",
        supporting_evidence=[],
    )
    perf_healthy_verdict = DiagnosisFinding(
        cause_id="PERF_ALL_HEALTHY",
        title="System Performance & Resources Optimal",
        description="Healthy",
        confidence=1.0,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="None",
        supporting_evidence=[],
    )
    mock_net_report = DiagnosisReport(
        domain="network",
        summary="DNS resolution failed",
        primary_finding=failing_verdict,
        all_findings=[failing_verdict],
    )
    mock_bth_report = DiagnosisReport(
        domain="bluetooth",
        summary="Healthy",
        primary_finding=bth_healthy_verdict,
        all_findings=[bth_healthy_verdict],
    )
    mock_drv_report = DiagnosisReport(
        domain="drivers",
        summary="Healthy",
        primary_finding=drv_healthy_verdict,
        all_findings=[drv_healthy_verdict],
    )
    mock_upd_report = DiagnosisReport(
        domain="update",
        summary="Healthy",
        primary_finding=upd_healthy_verdict,
        all_findings=[upd_healthy_verdict],
    )
    mock_sys_report = DiagnosisReport(
        domain="system",
        summary="Healthy",
        primary_finding=sys_healthy_verdict,
        all_findings=[sys_healthy_verdict],
    )
    mock_perf_report = DiagnosisReport(
        domain="performance",
        summary="Healthy",
        primary_finding=perf_healthy_verdict,
        all_findings=[perf_healthy_verdict],
    )
    mock_repair_result = RepairExecutionResult(
        repair_id="net.flush_dns",
        name="Flush and Reset DNS Cache",
        status=RepairStatus.SUCCESS,
        message="DNS resolution verified successfully.",
    )

    with patch("windoc.cli.run_all_network_checks", return_value=[]), \
         patch("windoc.domains.bluetooth.run_all_bluetooth_checks", return_value=[]), \
         patch("windoc.domains.drivers.run_all_driver_checks", return_value=[]), \
         patch("windoc.domains.update.run_all_update_checks", return_value=[]), \
         patch("windoc.domains.system.run_all_system_checks", return_value=[]), \
         patch("windoc.domains.performance.run_all_performance_checks", return_value=[]), \
         patch("windoc.core.engine.evaluate_network_hypotheses", return_value=mock_net_report), \
         patch("windoc.core.engine.evaluate_bluetooth_hypotheses", return_value=mock_bth_report), \
         patch("windoc.core.engine.evaluate_driver_hypotheses", return_value=mock_drv_report), \
         patch("windoc.core.engine.evaluate_update_hypotheses", return_value=mock_upd_report), \
         patch("windoc.core.engine.evaluate_system_hypotheses", return_value=mock_sys_report), \
         patch("windoc.core.engine.evaluate_performance_hypotheses", return_value=mock_perf_report), \
         patch("windoc.cli.execute_repair", return_value=mock_repair_result):
        result = runner.invoke(app, ["fix", "--yes"])
        assert result.exit_code == 0
        assert "Problem Detected:" in result.stdout
        assert "DNS Resolution Failure" in result.stdout
        assert "Fixed and Verified!" in result.stdout


def test_cli_repair_omitted_id_routes_to_fix() -> None:
    """Verify `windoc repair` or `windoc repair --yes` without ID routes to auto-fix."""
    from unittest.mock import patch

    with patch("windoc.cli.fix_cmd") as mock_fix:
        result = runner.invoke(app, ["repair", "--yes"])
        assert result.exit_code == 0
        mock_fix.assert_called_once_with(yes=True)


def test_cli_fix_specific_domain() -> None:
    """Verify `windoc fix network` only evaluates the network domain."""
    from unittest.mock import patch
    from windoc.core.engine import DiagnosisFinding, DiagnosisReport, HypothesisStatus

    healthy_verdict = DiagnosisFinding(
        cause_id="NET_ALL_HEALTHY",
        title="Network Operational",
        description="Healthy",
        confidence=1.0,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="None",
        supporting_evidence=[],
    )
    mock_net_report = DiagnosisReport(
        domain="network",
        summary="Healthy",
        primary_finding=healthy_verdict,
        all_findings=[healthy_verdict],
    )

    with patch("windoc.cli.run_all_network_checks", return_value=[]) as mock_net, \
         patch("windoc.domains.bluetooth.run_all_bluetooth_checks") as mock_bth, \
         patch("windoc.core.engine.evaluate_network_hypotheses", return_value=mock_net_report):
        result = runner.invoke(app, ["fix", "network"])
        assert result.exit_code == 0
        assert mock_net.called
        assert not mock_bth.called
        assert "All scanned subsystems are healthy" in result.stdout


def test_cli_fix_invalid_domain() -> None:
    """Verify `windoc fix invalid` produces a friendly error."""
    result = runner.invoke(app, ["fix", "invalid_domain"])
    assert result.exit_code == 1
    assert "Unknown domain 'invalid_domain'" in result.stdout


def test_cli_diagnose_domain_with_fix_flag() -> None:
    """Verify `windoc diagnose network --fix --yes` triggers automated repair."""
    from unittest.mock import patch
    from windoc.core.engine import DiagnosisFinding, DiagnosisReport, HypothesisStatus
    from windoc.repairs.models import RepairExecutionResult, RepairStatus

    failing_verdict = DiagnosisFinding(
        cause_id="NET_DNS_RESOLUTION_FAILED",
        title="DNS Resolution Failure",
        description="DNS failed",
        confidence=0.9,
        status=HypothesisStatus.CONFIRMED,
        recommended_action="Flush DNS",
        supporting_evidence=["socket failed"],
    )
    mock_net_report = DiagnosisReport(
        domain="network",
        summary="DNS resolution failed",
        primary_finding=failing_verdict,
        all_findings=[failing_verdict],
    )
    mock_repair_result = RepairExecutionResult(
        repair_id="net.flush_dns",
        name="Flush and Reset DNS Cache",
        status=RepairStatus.SUCCESS,
        message="DNS resolution verified successfully.",
    )

    with patch("windoc.cli.run_all_network_checks", return_value=[]), \
         patch("windoc.core.engine.evaluate_network_hypotheses", return_value=mock_net_report), \
         patch("windoc.cli.execute_repair", return_value=mock_repair_result):
        result = runner.invoke(app, ["diagnose", "network", "--fix", "--yes"])
        assert result.exit_code == 0
        assert "Problem Detected:" in result.stdout
        assert "DNS Resolution Failure" in result.stdout
        assert "Fixed and Verified!" in result.stdout




