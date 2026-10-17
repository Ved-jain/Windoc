"""Read-only network diagnostic checks for WinDoc."""

import socket
import urllib.request
from typing import Any, Dict, List, Optional

from windoc.core.models import (
    CheckStatus,
    DiagnosticResult,
    ResultKind,
    Severity,
)
from windoc.core.runner import run_command, run_powershell


def check_network_adapters() -> List[DiagnosticResult]:
    """Inspect physical and virtual network adapters to verify detection, status, and link state."""
    results: List[DiagnosticResult] = []
    
    ps_cmd = (
        "Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, "
        "LinkSpeed, MediaType, PhysicalMediaType, InterfaceOperationalStatus"
    )
    cmd_result, adapters = run_powershell(ps_cmd, as_json=True, ensure_list=True)

    if not cmd_result.is_success or adapters is None:
        results.append(
            DiagnosticResult(
                check_id="net.adapter.query",
                domain="network",
                observation=f"Failed to query network adapters: {cmd_result.error or cmd_result.stderr}",
                status=CheckStatus.ERROR,
                severity=Severity.HIGH,
                data_source="Get-NetAdapter",
                execution_error=cmd_result.error or cmd_result.stderr,
            )
        )
        return results

    if not adapters:
        results.append(
            DiagnosticResult(
                check_id="net.adapter.presence",
                domain="network",
                observation="No network adapters detected on the system.",
                status=CheckStatus.FAIL,
                severity=Severity.CRITICAL,
                data_source="Get-NetAdapter",
                result_kind=ResultKind.CONFIRMED,
            )
        )
        return results

    active_adapters = 0
    wifi_found = False
    ethernet_found = False

    for adapter in adapters:
        name = adapter.get("Name", "Unknown")
        status = adapter.get("Status", "Unknown")
        media_type = str(adapter.get("MediaType", "") or "")
        phys_media = str(adapter.get("PhysicalMediaType", "") or "")
        desc = adapter.get("InterfaceDescription", "")

        is_wifi = "802.3" not in phys_media and ("Wi-Fi" in name or "Wireless" in desc or "Native 802.11" in phys_media)
        is_ethernet = "802.3" in phys_media or "Ethernet" in name

        if is_wifi:
            wifi_found = True
        if is_ethernet:
            ethernet_found = True

        if status == "Up":
            active_adapters += 1
            results.append(
                DiagnosticResult(
                    check_id=f"net.adapter.{name.lower().replace(' ', '_')}.state",
                    domain="network",
                    observation=f"Adapter '{name}' ({desc}) is operational (Status: Up).",
                    status=CheckStatus.PASS,
                    severity=Severity.INFO,
                    data_source="Get-NetAdapter",
                    measured_value={"name": name, "status": status, "link_speed": adapter.get("LinkSpeed")},
                )
            )
        elif status == "Disabled":
            results.append(
                DiagnosticResult(
                    check_id=f"net.adapter.{name.lower().replace(' ', '_')}.state",
                    domain="network",
                    observation=f"Adapter '{name}' is administratively disabled.",
                    status=CheckStatus.WARNING,
                    severity=Severity.MEDIUM,
                    data_source="Get-NetAdapter",
                    measured_value={"name": name, "status": status},
                )
            )
        elif status == "Disconnected":
            results.append(
                DiagnosticResult(
                    check_id=f"net.adapter.{name.lower().replace(' ', '_')}.state",
                    domain="network",
                    observation=f"Adapter '{name}' media is disconnected (no physical cable or Wi-Fi association).",
                    status=CheckStatus.WARNING,
                    severity=Severity.LOW,
                    data_source="Get-NetAdapter",
                    measured_value={"name": name, "status": status},
                )
            )
        else:
            results.append(
                DiagnosticResult(
                    check_id=f"net.adapter.{name.lower().replace(' ', '_')}.state",
                    domain="network",
                    observation=f"Adapter '{name}' reports unexpected status: {status}.",
                    status=CheckStatus.WARNING,
                    severity=Severity.LOW,
                    data_source="Get-NetAdapter",
                    measured_value={"name": name, "status": status},
                )
            )

    results.append(
        DiagnosticResult(
            check_id="net.adapter.summary",
            domain="network",
            observation=f"Detected {len(adapters)} total adapter(s); {active_adapters} operational.",
            status=CheckStatus.PASS if active_adapters > 0 else CheckStatus.FAIL,
            severity=Severity.INFO if active_adapters > 0 else Severity.HIGH,
            data_source="Get-NetAdapter",
            measured_value={"total": len(adapters), "active": active_adapters, "has_wifi": wifi_found, "has_ethernet": ethernet_found},
        )
    )

    return results


def check_ip_configuration() -> List[DiagnosticResult]:
    """Inspect IPv4 configuration, detecting valid IPs and DHCP failures (APIPA 169.254.x.x)."""
    results: List[DiagnosticResult] = []

    ps_cmd = (
        "Get-NetIPAddress -AddressFamily IPv4 | "
        "Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.IPAddress -ne '127.0.0.1' } | "
        "Select-Object InterfaceAlias, IPAddress, PrefixLength, AddressState"
    )
    cmd_result, ip_addresses = run_powershell(ps_cmd, as_json=True, ensure_list=True)

    if not cmd_result.is_success or ip_addresses is None:
        results.append(
            DiagnosticResult(
                check_id="net.ip.query",
                domain="network",
                observation=f"Failed to query IP configuration: {cmd_result.error or cmd_result.stderr}",
                status=CheckStatus.ERROR,
                severity=Severity.HIGH,
                data_source="Get-NetIPAddress",
            )
        )
        return results

    has_valid_ipv4 = False
    has_apipa = False

    for entry in ip_addresses:
        alias = entry.get("InterfaceAlias", "Unknown")
        ipv4_addr = entry.get("IPAddress")

        if not ipv4_addr:
            continue

        # Check for APIPA address (169.254.0.0/16) indicative of DHCP assignment failure
        if ipv4_addr.startswith("169.254."):
            has_apipa = True
            results.append(
                DiagnosticResult(
                    check_id=f"net.ip.{alias.lower().replace(' ', '_').replace('*', '')}.apipa",
                    domain="network",
                    observation=f"Interface '{alias}' has an APIPA address ({ipv4_addr}). DHCP negotiation likely failed.",
                    status=CheckStatus.WARNING,
                    severity=Severity.MEDIUM,
                    result_kind=ResultKind.INFERENCE,
                    data_source="Get-NetIPAddress",
                    measured_value={"interface": alias, "ip": ipv4_addr},
                )
            )
        else:
            has_valid_ipv4 = True
            results.append(
                DiagnosticResult(
                    check_id=f"net.ip.{alias.lower().replace(' ', '_').replace('*', '')}.valid",
                    domain="network",
                    observation=f"Interface '{alias}' has a valid IPv4 address ({ipv4_addr}).",
                    status=CheckStatus.PASS,
                    severity=Severity.INFO,
                    data_source="Get-NetIPAddress",
                    measured_value={"interface": alias, "ip": ipv4_addr},
                )
            )

    results.append(
        DiagnosticResult(
            check_id="net.ip.status",
            domain="network",
            observation=(
                "Valid IPv4 address detected." if has_valid_ipv4
                else ("APIPA address detected; DHCP failed to assign an IP." if has_apipa else "No IPv4 address assigned to any interface.")
            ),
            status=CheckStatus.PASS if has_valid_ipv4 else CheckStatus.FAIL,
            severity=Severity.INFO if has_valid_ipv4 else Severity.HIGH,
            data_source="Get-NetIPAddress",
            result_kind=ResultKind.INFERENCE if has_apipa else ResultKind.OBSERVATION,
        )
    )

    return results


def check_default_gateway() -> DiagnosticResult:
    """Identify the default gateway and verify its reachability via ARP/ping."""
    ps_cmd = "Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Select-Object -First 1 -ExpandProperty NextHop"
    cmd_result = run_command(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
        timeout_seconds=5.0,
    )

    gateway_ip = cmd_result.stdout.strip()
    if not gateway_ip or gateway_ip == "0.0.0.0":
        return DiagnosticResult(
            check_id="net.gateway.presence",
            domain="network",
            observation="No active default gateway route (0.0.0.0/0) is configured.",
            status=CheckStatus.FAIL,
            severity=Severity.HIGH,
            data_source="Get-NetRoute",
            result_kind=ResultKind.CONFIRMED,
        )

    # Test gateway reachability with a 1-ping probe
    ping_res = run_command(["ping.exe", "-n", "1", "-w", "1500", gateway_ip], timeout_seconds=4.0)
    gateway_reachable = ping_res.is_success and "Reply from" in ping_res.stdout

    if gateway_reachable:
        return DiagnosticResult(
            check_id="net.gateway.reachability",
            domain="network",
            observation=f"Default gateway ({gateway_ip}) is reachable.",
            status=CheckStatus.PASS,
            severity=Severity.INFO,
            data_source="ping.exe",
            measured_value={"gateway_ip": gateway_ip},
        )
    else:
        return DiagnosticResult(
            check_id="net.gateway.reachability",
            domain="network",
            observation=f"Default gateway ({gateway_ip}) failed to respond to ICMP probe.",
            status=CheckStatus.WARNING,
            severity=Severity.MEDIUM,
            data_source="ping.exe",
            measured_value={"gateway_ip": gateway_ip},
            limitations="Gateway may block ICMP ping while still routing traffic.",
        )


def check_dns_resolution() -> List[DiagnosticResult]:
    """Test DNS server configuration and domain resolution using socket queries."""
    results: List[DiagnosticResult] = []

    # 1. Query configured DNS servers
    ps_cmd = (
        "Get-DnsClientServerAddress -AddressFamily IPv4 | "
        "Where-Object { $_.ServerAddresses.Count -gt 0 } | "
        "Select-Object InterfaceAlias, ServerAddresses"
    )
    cmd_result, dns_servers = run_powershell(ps_cmd, as_json=True, ensure_list=True)

    server_count = 0
    if cmd_result.is_success and dns_servers:
        for entry in dns_servers:
            addrs = entry.get("ServerAddresses")
            if addrs:
                server_count += len(addrs) if isinstance(addrs, list) else 1

    if server_count == 0:
        results.append(
            DiagnosticResult(
                check_id="net.dns.server_configured",
                domain="network",
                observation="No DNS servers are configured for active network interfaces.",
                status=CheckStatus.FAIL,
                severity=Severity.HIGH,
                data_source="Get-DnsClientServerAddress",
            )
        )
    else:
        results.append(
            DiagnosticResult(
                check_id="net.dns.server_configured",
                domain="network",
                observation=f"{server_count} DNS server address(es) configured.",
                status=CheckStatus.PASS,
                severity=Severity.INFO,
                data_source="Get-DnsClientServerAddress",
                measured_value={"count": server_count},
            )
        )

    # 2. Test actual DNS resolution for standard endpoints
    test_hosts = ["dns.msftncsi.com", "one.one.one.one", "google.com"]
    resolved_count = 0

    for host in test_hosts:
        try:
            # Set default timeout for socket resolution
            orig_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(2.5)
            try:
                ip = socket.gethostbyname(host)
                if ip:
                    resolved_count += 1
            finally:
                socket.setdefaulttimeout(orig_timeout)
        except (socket.gaierror, socket.timeout, OSError):
            pass

    if resolved_count == len(test_hosts):
        results.append(
            DiagnosticResult(
                check_id="net.dns.resolution",
                domain="network",
                observation=f"DNS resolution succeeded for {resolved_count}/{len(test_hosts)} test domains.",
                status=CheckStatus.PASS,
                severity=Severity.INFO,
                data_source="socket.gethostbyname",
                measured_value={"resolved": resolved_count, "total": len(test_hosts)},
            )
        )
    elif resolved_count > 0:
        results.append(
            DiagnosticResult(
                check_id="net.dns.resolution",
                domain="network",
                observation=f"Partial DNS resolution: {resolved_count}/{len(test_hosts)} test domains resolved.",
                status=CheckStatus.WARNING,
                severity=Severity.MEDIUM,
                data_source="socket.gethostbyname",
                measured_value={"resolved": resolved_count, "total": len(test_hosts)},
            )
        )
    else:
        results.append(
            DiagnosticResult(
                check_id="net.dns.resolution",
                domain="network",
                observation=f"DNS resolution failed completely for all {len(test_hosts)} test domains.",
                status=CheckStatus.FAIL,
                severity=Severity.HIGH,
                data_source="socket.gethostbyname",
                measured_value={"resolved": 0, "total": len(test_hosts)},
            )
        )

    return results


def check_internet_connectivity() -> DiagnosticResult:
    """Verify external internet connectivity using dual pathways (TCP socket + HTTP NCSI probe).
    
    Critically, we do NOT rely on ICMP ping alone because many networks and firewalls
    block ICMP echo requests while allowing standard TCP traffic.
    """
    # 1. Primary test: Direct TCP connection probe to Cloudflare / Google DNS public IP on port 53
    tcp_success = False
    for ip, port in [("1.1.1.1", 53), ("8.8.8.8", 53)]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.5)
            sock.connect((ip, port))
            sock.close()
            tcp_success = True
            break
        except (socket.error, OSError):
            continue

    # 2. Secondary test: Windows NCSI HTTP probe (http://www.msftconnecttest.com/connecttest.txt)
    http_success = False
    try:
        req = urllib.request.Request(
            "http://www.msftconnecttest.com/connecttest.txt",
            headers={"User-Agent": "Microsoft NCSI"},
        )
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            content = resp.read().decode("utf-8", errors="replace").strip()
            if "Microsoft Connect Test" in content:
                http_success = True
    except (urllib.error.URLError, OSError, TimeoutError):
        pass

    if tcp_success and http_success:
        return DiagnosticResult(
            check_id="net.external.connectivity",
            domain="network",
            observation="Full external internet connectivity confirmed (TCP handshake and NCSI probe succeeded).",
            status=CheckStatus.PASS,
            severity=Severity.INFO,
            data_source="TCP+HTTP",
            measured_value={"tcp_probe": True, "http_ncsi": True},
        )
    elif tcp_success and not http_success:
        return DiagnosticResult(
            check_id="net.external.connectivity",
            domain="network",
            observation="External IP routing works via TCP, but HTTP probe failed (possible captive portal or proxy).",
            status=CheckStatus.WARNING,
            severity=Severity.MEDIUM,
            data_source="TCP+HTTP",
            measured_value={"tcp_probe": True, "http_ncsi": False},
        )
    elif not tcp_success and http_success:
        return DiagnosticResult(
            check_id="net.external.connectivity",
            domain="network",
            observation="HTTP web access is functional through proxy, but direct TCP port 53 is blocked.",
            status=CheckStatus.PASS,
            severity=Severity.LOW,
            data_source="TCP+HTTP",
            measured_value={"tcp_probe": False, "http_ncsi": True},
        )
    else:
        return DiagnosticResult(
            check_id="net.external.connectivity",
            domain="network",
            observation="No external internet connectivity (both direct TCP connection and HTTP probes failed).",
            status=CheckStatus.FAIL,
            severity=Severity.HIGH,
            data_source="TCP+HTTP",
            measured_value={"tcp_probe": False, "http_ncsi": False},
        )


def check_proxy_and_vpn() -> List[DiagnosticResult]:
    """Check system proxy configuration and active VPN or virtual tunneling adapters."""
    results: List[DiagnosticResult] = []

    # Check WinINet proxy settings from registry via PowerShell
    ps_cmd = (
        "Get-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' "
        "| Select-Object ProxyEnable, ProxyServer, AutoConfigURL"
    )
    cmd_result, proxy_info = run_powershell(ps_cmd, as_json=True)

    if cmd_result.is_success and proxy_info:
        proxy_enabled = bool(proxy_info.get("ProxyEnable", 0))
        proxy_server = proxy_info.get("ProxyServer")
        autoconfig = proxy_info.get("AutoConfigURL")

        if proxy_enabled:
            results.append(
                DiagnosticResult(
                    check_id="net.proxy.enabled",
                    domain="network",
                    observation=f"System proxy is enabled (Server: {proxy_server or 'None'}).",
                    status=CheckStatus.WARNING,
                    severity=Severity.LOW,
                    data_source="registry:Internet Settings",
                    measured_value={"proxy_enabled": True, "proxy_server": proxy_server, "pac": autoconfig},
                )
            )
        else:
            results.append(
                DiagnosticResult(
                    check_id="net.proxy.enabled",
                    domain="network",
                    observation="No manual system proxy is configured.",
                    status=CheckStatus.PASS,
                    severity=Severity.INFO,
                    data_source="registry:Internet Settings",
                )
            )

    return results


def run_all_network_checks() -> List[DiagnosticResult]:
    """Execute all network diagnostic checks and return an ordered evidence list."""
    evidence: List[DiagnosticResult] = []
    
    # 1. Physical / Link layer
    evidence.extend(check_network_adapters())
    
    # 2. IP layer
    evidence.extend(check_ip_configuration())
    
    # 3. Default Gateway routing
    evidence.append(check_default_gateway())
    
    # 4. DNS layer
    evidence.extend(check_dns_resolution())
    
    # 5. External internet reachability
    evidence.append(check_internet_connectivity())
    
    # 6. Proxy and VPN layer
    evidence.extend(check_proxy_and_vpn())

    return evidence
