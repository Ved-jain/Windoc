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
    """Verify `windoc scan` command triggers diagnostic scans."""
    from unittest.mock import patch
    from windoc.core.models import CheckStatus, DiagnosticResult

    mock_result = DiagnosticResult(
        check_id="net.dns.test",
        domain="network",
        observation="DNS test passed",
        status=CheckStatus.PASS,
        data_source="socket",
    )
    with patch("windoc.cli.run_all_network_checks", return_value=[mock_result]):
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "Starting comprehensive diagnostic scan" in result.stdout
        assert "Network Diagnostics" in result.stdout
        assert "net.dns.test" in result.stdout
        assert "PASS" in result.stdout


def test_cli_list_repairs() -> None:
    """Verify `windoc list-repairs` displays allowlisted repair table."""
    result = runner.invoke(app, ["list-repairs"])
    assert result.exit_code == 0
    assert "Controlled Repair Registry" in result.stdout
    assert "net.flush_dns" in result.stdout
    assert "net.renew_dhcp" in result.stdout


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


