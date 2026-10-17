"""Unit tests for the network diagnostic checks."""

from unittest.mock import MagicMock, patch
import pytest

from windoc.core.models import CheckStatus, DiagnosticResult, ResultKind, Severity
from windoc.core.runner import CommandResult
from windoc.domains.network.checks import (
    check_default_gateway,
    check_dns_resolution,
    check_internet_connectivity,
    check_ip_configuration,
    check_network_adapters,
    check_proxy_and_vpn,
    run_all_network_checks,
)


def test_check_network_adapters_operational() -> None:
    """Test adapter check when active operational adapters exist."""
    mock_adapters = [
        {
            "Name": "Wi-Fi",
            "InterfaceDescription": "Intel(R) Wi-Fi 6 AX201 160MHz",
            "Status": "Up",
            "LinkSpeed": "1.2 Gbps",
            "MediaType": "Native 802.11",
            "PhysicalMediaType": "Native 802.11",
        },
        {
            "Name": "Ethernet",
            "InterfaceDescription": "Realtek PCIe GbE Family Controller",
            "Status": "Disconnected",
            "LinkSpeed": "0 bps",
            "MediaType": "802.3",
            "PhysicalMediaType": "802.3",
        },
    ]

    with patch("windoc.domains.network.checks.run_powershell") as mock_ps:
        mock_ps.return_value = (
            CommandResult(args=["Get-NetAdapter"], exit_code=0, stdout="...", duration_ms=10.0),
            mock_adapters,
        )
        results = check_network_adapters()

        assert len(results) == 3  # 2 adapters + 1 summary
        # Wi-Fi check
        assert results[0].status == CheckStatus.PASS
        assert "operational" in results[0].observation
        # Ethernet check
        assert results[1].status == CheckStatus.WARNING
        assert "disconnected" in results[1].observation
        # Summary
        assert results[2].status == CheckStatus.PASS
        assert results[2].measured_value["has_wifi"] is True


def test_check_network_adapters_empty() -> None:
    """Test adapter check when no adapters are detected."""
    with patch("windoc.domains.network.checks.run_powershell") as mock_ps:
        mock_ps.return_value = (
            CommandResult(args=["Get-NetAdapter"], exit_code=0, stdout="", duration_ms=10.0),
            [],
        )
        results = check_network_adapters()
        assert len(results) == 1
        assert results[0].status == CheckStatus.FAIL
        assert results[0].severity == Severity.CRITICAL


def test_check_ip_configuration_apipa_dhcp_failure() -> None:
    """Test APIPA (169.254.x.x) detection indicating DHCP assignment failure."""
    mock_configs = [
        {
            "InterfaceAlias": "Wi-Fi",
            "IPAddress": "169.254.45.101",
        }
    ]

    with patch("windoc.domains.network.checks.run_powershell") as mock_ps:
        mock_ps.return_value = (
            CommandResult(args=["Get-NetIPAddress"], exit_code=0, stdout="...", duration_ms=10.0),
            mock_configs,
        )
        results = check_ip_configuration()

        assert len(results) == 2
        apipa_result = results[0]
        assert apipa_result.status == CheckStatus.WARNING
        assert apipa_result.severity == Severity.MEDIUM
        assert apipa_result.result_kind == ResultKind.INFERENCE
        assert "APIPA" in apipa_result.observation
        assert "DHCP negotiation likely failed" in apipa_result.observation


def test_check_ip_configuration_valid_ipv4() -> None:
    """Test valid IPv4 address detection."""
    mock_configs = [
        {
            "InterfaceAlias": "Ethernet",
            "IPAddress": "192.168.1.150",
        }
    ]

    with patch("windoc.domains.network.checks.run_powershell") as mock_ps:
        mock_ps.return_value = (
            CommandResult(args=["Get-NetIPAddress"], exit_code=0, stdout="...", duration_ms=10.0),
            mock_configs,
        )
        results = check_ip_configuration()

        assert len(results) == 2
        assert results[0].status == CheckStatus.PASS
        assert "valid IPv4 address" in results[0].observation
        assert results[1].status == CheckStatus.PASS


def test_check_default_gateway_missing() -> None:
    """Test default gateway check when no gateway is configured."""
    with patch("windoc.domains.network.checks.run_command") as mock_run:
        mock_run.return_value = CommandResult(args=["Get-NetRoute"], exit_code=0, stdout="", duration_ms=10.0)
        result = check_default_gateway()

        assert result.status == CheckStatus.FAIL
        assert result.check_id == "net.gateway.presence"


def test_check_default_gateway_ping_success() -> None:
    """Test gateway reachability when ping replies."""
    with patch("windoc.domains.network.checks.run_command") as mock_run:
        mock_run.side_effect = [
            CommandResult(args=["Get-NetRoute"], exit_code=0, stdout="192.168.1.1", duration_ms=10.0),
            CommandResult(args=["ping.exe"], exit_code=0, stdout="Reply from 192.168.1.1: bytes=32 time=1ms TTL=64", duration_ms=10.0),
        ]
        result = check_default_gateway()

        assert result.status == CheckStatus.PASS
        assert "reachable" in result.observation


def test_check_internet_connectivity_success() -> None:
    """Test external connectivity when TCP probe and HTTP NCSI probe succeed."""
    with patch("socket.socket") as mock_sock_cls, patch("urllib.request.urlopen") as mock_urlopen:
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        mock_sock.connect.return_value = None

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"Microsoft Connect Test"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = check_internet_connectivity()
        assert result.status == CheckStatus.PASS
        assert "Full external internet connectivity confirmed" in result.observation


def test_check_internet_connectivity_failure() -> None:
    """Test external connectivity when both TCP and HTTP fail."""
    with patch("socket.socket") as mock_sock_cls, patch("urllib.request.urlopen") as mock_urlopen:
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        mock_sock.connect.side_effect = OSError("Host unreachable")
        mock_urlopen.side_effect = OSError("Network down")

        result = check_internet_connectivity()
        assert result.status == CheckStatus.FAIL
        assert "No external internet connectivity" in result.observation


def test_run_all_network_checks_aggregates_evidence() -> None:
    """Test that run_all_network_checks aggregates results across all layers."""
    with patch("windoc.domains.network.checks.check_network_adapters") as m_adap, \
         patch("windoc.domains.network.checks.check_ip_configuration") as m_ip, \
         patch("windoc.domains.network.checks.check_default_gateway") as m_gw, \
         patch("windoc.domains.network.checks.check_dns_resolution") as m_dns, \
         patch("windoc.domains.network.checks.check_internet_connectivity") as m_inet, \
         patch("windoc.domains.network.checks.check_proxy_and_vpn") as m_proxy:

        dummy_res = DiagnosticResult(
            check_id="test.check",
            domain="network",
            observation="Test observation",
            status=CheckStatus.PASS,
        )

        m_adap.return_value = [dummy_res]
        m_ip.return_value = [dummy_res]
        m_gw.return_value = dummy_res
        m_dns.return_value = [dummy_res]
        m_inet.return_value = dummy_res
        m_proxy.return_value = [dummy_res]

        results = run_all_network_checks()
        assert len(results) == 6
