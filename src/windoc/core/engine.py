"""Deterministic evidence-driven hypothesis engine for WinDoc."""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from windoc.core.models import CheckStatus, DiagnosticResult, Severity


class HypothesisStatus(str, Enum):
    """Categorical assessment of a hypothesis based on accumulated evidence."""
    CONFIRMED = "CONFIRMED"        # Substantial evidence; confidence >= 80%
    LIKELY = "LIKELY"              # Leading explanation; confidence >= 50%
    POSSIBLE = "POSSIBLE"          # Incomplete evidence; confidence >= 25%
    RULED_OUT = "RULED_OUT"        # Strong contradicting evidence; confidence <= 10%
    INCONCLUSIVE = "INCONCLUSIVE"  # Evidence conflicting or insufficient


class DiagnosisFinding(BaseModel):
    """A single evaluated hypothesis explaining the observed state."""
    cause_id: str = Field(..., description="Unique machine-readable cause identifier")
    title: str = Field(..., description="Human-readable title of the root cause")
    description: str = Field(..., description="Explanation of what this root cause means")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Normalized confidence score (0.0 to 1.0)")
    status: HypothesisStatus = Field(..., description="Categorical evaluation status")
    supporting_evidence: List[str] = Field(default_factory=list, description="Observations that support this cause")
    refuting_evidence: List[str] = Field(default_factory=list, description="Observations that contradict this cause")
    recommended_action: str = Field(..., description="Next diagnostic test or proposed repair direction")


class DiagnosisReport(BaseModel):
    """Comprehensive diagnostic verdict produced by the hypothesis engine."""
    domain: str = Field(..., description="Problem domain diagnosed")
    primary_finding: Optional[DiagnosisFinding] = Field(default=None, description="Leading root cause if conclusive")
    all_findings: List[DiagnosisFinding] = Field(default_factory=list, description="All evaluated candidate hypotheses")
    evidence_count: int = Field(default=0, description="Total diagnostic checks analyzed")
    is_conclusive: bool = Field(default=False, description="Whether a decisive diagnosis was established")
    summary: str = Field(..., description="High-level conclusion for the user")


def evaluate_network_hypotheses(evidence: List[DiagnosticResult]) -> DiagnosisReport:
    """Evaluate network domain evidence using transparent, deterministic scoring rules.
    
    Interview Defense:
    Each hypothesis maintains an explicit score. Each diagnostic check provides positive
    evidence weight (+support) or negative refutation weight (-refute).
    The scores are clamped to [0, 100] and normalized to a [0.0, 1.0] confidence score.
    """
    evidence_by_id: Dict[str, DiagnosticResult] = {r.check_id: r for r in evidence}
    
    # 1. Candidate Hypothesis Initial Definitions
    candidates = [
        {
            "cause_id": "NET_ALL_HEALTHY",
            "title": "All Network Subsystems Operational",
            "description": "Network adapters, IP configuration, gateway, DNS, and external reachability are functional.",
            "recommended_action": "No repair needed; network is fully operational.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "NET_PHYSICAL_DISCONNECTED",
            "title": "Physical Media Disconnected or Disabled",
            "description": "No active operational network adapters detected, or Wi-Fi radio is off / cable unplugged.",
            "recommended_action": "Reconnect the Ethernet cable, toggle Wi-Fi radio on, or enable disabled adapter.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "NET_DHCP_LEASE_FAILED",
            "title": "DHCP Address Assignment Failed (APIPA Active)",
            "description": "The system received no IP from the local router/DHCP server and defaulted to an auto-assigned 169.254.x.x address.",
            "recommended_action": "Release and renew DHCP lease or verify DHCP server / router status.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "NET_GATEWAY_UNREACHABLE",
            "title": "Default Gateway Unreachable",
            "description": "The local router or default gateway route is missing or not responding to traffic.",
            "recommended_action": "Restart the local router or verify subnet IP and default route settings.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "NET_DNS_RESOLUTION_FAILED",
            "title": "DNS Server Unresponsive or Misconfigured",
            "description": "Network routing is functional, but the configured DNS servers cannot resolve domain names.",
            "recommended_action": "Flush local DNS cache or switch DNS to a public resolver (e.g. 1.1.1.1 or 8.8.8.8).",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "NET_CAPTIVE_PORTAL_OR_PROXY",
            "title": "Captive Portal or Proxy Interception",
            "description": "Direct TCP traffic is routed, but HTTP web probes are intercepted or blocked (common on public Wi-Fi).",
            "recommended_action": "Open a web browser to complete public network login / sign-in portal.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
    ]

    c_map = {c["cause_id"]: c for c in candidates}

    # 2. Rule-Based Evidence Evaluation
    # Check 1: Adapter summary & active count
    adap_summary = evidence_by_id.get("net.adapter.summary")
    if adap_summary:
        if adap_summary.status == CheckStatus.PASS:
            c_map["NET_ALL_HEALTHY"]["score"] += 20
            c_map["NET_ALL_HEALTHY"]["supports"].append("Network adapters detected and operational.")
            c_map["NET_PHYSICAL_DISCONNECTED"]["score"] -= 50
            c_map["NET_PHYSICAL_DISCONNECTED"]["refutes"].append("Operational network adapter is active.")
        else:
            c_map["NET_PHYSICAL_DISCONNECTED"]["score"] += 60
            c_map["NET_PHYSICAL_DISCONNECTED"]["supports"].append("No operational network adapters detected.")
            c_map["NET_ALL_HEALTHY"]["score"] -= 80
            c_map["NET_ALL_HEALTHY"]["refutes"].append("No operational network adapters.")

    # Check 2: IP Configuration & APIPA
    ip_status = evidence_by_id.get("net.ip.status")
    has_valid_ip = ip_status is not None and ip_status.status == CheckStatus.PASS
    has_apipa = any("apipa" in k and r.status == CheckStatus.WARNING for k, r in evidence_by_id.items())
    
    if has_apipa and not has_valid_ip:
        c_map["NET_DHCP_LEASE_FAILED"]["score"] += 90
        c_map["NET_DHCP_LEASE_FAILED"]["supports"].append("Interface has an APIPA (169.254.x.x) address and no valid IP exists.")
        c_map["NET_ALL_HEALTHY"]["score"] -= 80
        c_map["NET_ALL_HEALTHY"]["refutes"].append("APIPA address indicates DHCP assignment failure.")
        c_map["NET_GATEWAY_UNREACHABLE"]["score"] -= 40
        c_map["NET_GATEWAY_UNREACHABLE"]["refutes"].append("Missing gateway is a downstream symptom of DHCP failure.")
    elif has_valid_ip:
        c_map["NET_ALL_HEALTHY"]["score"] += 25
        c_map["NET_ALL_HEALTHY"]["supports"].append("Valid IPv4 address assigned to active interface.")
        c_map["NET_DHCP_LEASE_FAILED"]["score"] -= 70
        c_map["NET_DHCP_LEASE_FAILED"]["refutes"].append("Valid routable IPv4 address is present on active interface.")

    # Check 3: Default Gateway Reachability
    gw_pres = evidence_by_id.get("net.gateway.presence")
    gw_reach = evidence_by_id.get("net.gateway.reachability")

    if gw_pres and gw_pres.status == CheckStatus.FAIL:
        if not has_apipa:
            c_map["NET_GATEWAY_UNREACHABLE"]["score"] += 80
            c_map["NET_GATEWAY_UNREACHABLE"]["supports"].append("No active default gateway route configured.")
        c_map["NET_ALL_HEALTHY"]["score"] -= 80
        c_map["NET_ALL_HEALTHY"]["refutes"].append("Default gateway is absent.")
    elif gw_reach:
        if gw_reach.status == CheckStatus.PASS:
            c_map["NET_ALL_HEALTHY"]["score"] += 20
            c_map["NET_ALL_HEALTHY"]["supports"].append("Default gateway responded to reachability probe.")
            c_map["NET_GATEWAY_UNREACHABLE"]["score"] -= 70
            c_map["NET_GATEWAY_UNREACHABLE"]["refutes"].append("Default gateway is reachable.")
        elif gw_reach.status == CheckStatus.WARNING:
            if not has_apipa:
                c_map["NET_GATEWAY_UNREACHABLE"]["score"] += 50
                c_map["NET_GATEWAY_UNREACHABLE"]["supports"].append("Default gateway failed ICMP probe.")

    # Check 4: DNS Resolution
    dns_res = evidence_by_id.get("net.dns.resolution")
    if dns_res:
        if dns_res.status == CheckStatus.PASS:
            c_map["NET_ALL_HEALTHY"]["score"] += 20
            c_map["NET_ALL_HEALTHY"]["supports"].append("DNS resolution succeeded for all test domains.")
            c_map["NET_DNS_RESOLUTION_FAILED"]["score"] -= 80
            c_map["NET_DNS_RESOLUTION_FAILED"]["refutes"].append("DNS resolution is functional.")
        elif dns_res.status in (CheckStatus.FAIL, CheckStatus.WARNING):
            c_map["NET_DNS_RESOLUTION_FAILED"]["score"] += 65
            c_map["NET_DNS_RESOLUTION_FAILED"]["supports"].append("Domain name resolution failed or timed out.")
            c_map["NET_ALL_HEALTHY"]["score"] -= 70
            c_map["NET_ALL_HEALTHY"]["refutes"].append("DNS resolution failed.")

    # Check 5: External Reachability (Dual Pathway)
    ext_conn = evidence_by_id.get("net.external.connectivity")
    if ext_conn:
        if ext_conn.status == CheckStatus.PASS:
            c_map["NET_ALL_HEALTHY"]["score"] += 50
            c_map["NET_ALL_HEALTHY"]["supports"].append("External internet connectivity confirmed via TCP and HTTP.")
            c_map["NET_CAPTIVE_PORTAL_OR_PROXY"]["score"] -= 60
            c_map["NET_CAPTIVE_PORTAL_OR_PROXY"]["refutes"].append("Direct internet probes succeeded.")
            c_map["NET_DHCP_LEASE_FAILED"]["score"] -= 70
            c_map["NET_DHCP_LEASE_FAILED"]["refutes"].append("Active interface has working external connectivity.")
        elif ext_conn.status == CheckStatus.WARNING:
            # TCP works, but HTTP NCSI failed -> Captive portal signature!
            c_map["NET_CAPTIVE_PORTAL_OR_PROXY"]["score"] += 75
            c_map["NET_CAPTIVE_PORTAL_OR_PROXY"]["supports"].append("TCP port 53 succeeded but HTTP probe failed (captive portal signature).")
            c_map["NET_ALL_HEALTHY"]["score"] -= 50
        elif ext_conn.status == CheckStatus.FAIL:
            c_map["NET_ALL_HEALTHY"]["score"] -= 80
            c_map["NET_ALL_HEALTHY"]["refutes"].append("External internet connectivity is unavailable.")

    # 3. Score Normalization and Status Determination
    findings: List[DiagnosisFinding] = []
    for c in candidates:
        raw_score = max(0.0, min(100.0, c["score"]))
        confidence = round(raw_score / 100.0, 2)

        if confidence >= 0.80:
            status = HypothesisStatus.CONFIRMED
        elif confidence >= 0.50:
            status = HypothesisStatus.LIKELY
        elif confidence >= 0.25:
            status = HypothesisStatus.POSSIBLE
        elif confidence <= 0.10:
            status = HypothesisStatus.RULED_OUT
        else:
            status = HypothesisStatus.INCONCLUSIVE

        findings.append(
            DiagnosisFinding(
                cause_id=c["cause_id"],
                title=c["title"],
                description=c["description"],
                confidence=confidence,
                status=status,
                supporting_evidence=c["supports"],
                refuting_evidence=c["refutes"],
                recommended_action=c["recommended_action"],
            )
        )

    # Sort findings by confidence descending
    findings.sort(key=lambda f: f.confidence, reverse=True)
    primary = findings[0] if findings and findings[0].confidence >= 0.50 else None

    # High-level conclusion summary
    if primary and primary.status == HypothesisStatus.CONFIRMED:
        summary = f"Confirmed root cause: {primary.title} (Confidence: {int(primary.confidence * 100)}%)."
    elif primary and primary.status == HypothesisStatus.LIKELY:
        summary = f"Probable root cause: {primary.title} (Confidence: {int(primary.confidence * 100)}%)."
    else:
        summary = "Diagnostic evidence is inconclusive; manual investigation required."

    return DiagnosisReport(
        domain="network",
        primary_finding=primary,
        all_findings=findings,
        evidence_count=len(evidence),
        is_conclusive=primary is not None and primary.status in (HypothesisStatus.CONFIRMED, HypothesisStatus.LIKELY),
        summary=summary,
    )


def evaluate_bluetooth_hypotheses(evidence: List[DiagnosticResult]) -> DiagnosisReport:
    """Evaluate Bluetooth diagnostic evidence using deterministic, transparent scoring rules."""
    evidence_by_id: Dict[str, DiagnosticResult] = {r.check_id: r for r in evidence}

    candidates = [
        {
            "cause_id": "BTH_ALL_HEALTHY",
            "title": "All Bluetooth Subsystems Operational",
            "description": "Bluetooth Support Service is active and controller hardware is fully operational.",
            "recommended_action": "No repair needed; Bluetooth subsystem is functioning normally.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "BTH_SERVICE_STOPPED",
            "title": "Bluetooth Support Service (bthserv) Stopped",
            "description": "The Windows Bluetooth Support Service is stopped or disabled, blocking Bluetooth communications.",
            "recommended_action": "Restart the Bluetooth Support Service (bthserv).",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "BTH_ADAPTER_MISSING",
            "title": "Bluetooth Controller Hardware Missing",
            "description": "Windows does not detect any Bluetooth radio hardware connected to the motherboard or USB bus.",
            "recommended_action": "Connect a USB Bluetooth adapter or verify motherboard / BIOS device settings.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "BTH_ADAPTER_DISABLED",
            "title": "Bluetooth Controller Administratively Disabled",
            "description": "The Bluetooth radio controller is present but disabled in Windows Device Manager (Code 22).",
            "recommended_action": "Enable the Bluetooth controller in Device Manager or via WinDoc repair.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "BTH_DRIVER_DEVICE_ERROR",
            "title": "Bluetooth Hardware or Driver Error",
            "description": "The Bluetooth controller reported a driver initialization or device descriptor failure (Code 10/43).",
            "recommended_action": "Reinstall or update the Bluetooth manufacturer driver or power-cycle the machine.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "BTH_PERIPHERAL_ERROR",
            "title": "Individual Bluetooth Peripheral Error",
            "description": "The core Bluetooth adapter is operational, but a specific peripheral reported error codes.",
            "recommended_action": "Unpair and re-pair the affected Bluetooth accessory.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
    ]

    c_map = {c["cause_id"]: c for c in candidates}

    # 1. Service state evaluation
    svc_check = evidence_by_id.get("bth.service.bthserv.state")
    if svc_check:
        if svc_check.status == CheckStatus.PASS:
            c_map["BTH_ALL_HEALTHY"]["score"] += 50
            c_map["BTH_ALL_HEALTHY"]["supports"].append("Bluetooth Support Service is running.")
            c_map["BTH_SERVICE_STOPPED"]["score"] -= 90
            c_map["BTH_SERVICE_STOPPED"]["refutes"].append("Bluetooth Support Service is running.")
        else:
            c_map["BTH_SERVICE_STOPPED"]["score"] += 90
            c_map["BTH_SERVICE_STOPPED"]["supports"].append("Bluetooth Support Service is stopped or disabled.")
            c_map["BTH_ALL_HEALTHY"]["score"] -= 80
            c_map["BTH_ALL_HEALTHY"]["refutes"].append("Bluetooth Support Service is not running.")

    # 2. Adapter controller presence & state evaluation
    presence_check = evidence_by_id.get("bth.adapter.presence")
    operational_check = evidence_by_id.get("bth.adapter.operational")
    disabled_check = evidence_by_id.get("bth.adapter.disabled")
    driver_error_check = evidence_by_id.get("bth.adapter.driver_error")

    if presence_check and presence_check.status == CheckStatus.FAIL:
        c_map["BTH_ADAPTER_MISSING"]["score"] += 100
        c_map["BTH_ADAPTER_MISSING"]["supports"].append("No physical Bluetooth controller hardware detected.")
        c_map["BTH_ALL_HEALTHY"]["score"] -= 100
        c_map["BTH_ALL_HEALTHY"]["refutes"].append("No Bluetooth adapter hardware detected.")
    elif operational_check and operational_check.status == CheckStatus.PASS:
        c_map["BTH_ALL_HEALTHY"]["score"] += 50
        c_map["BTH_ALL_HEALTHY"]["supports"].append("Physical Bluetooth controller is operational.")
        c_map["BTH_ADAPTER_MISSING"]["score"] -= 90
        c_map["BTH_ADAPTER_DISABLED"]["score"] -= 90
        c_map["BTH_DRIVER_DEVICE_ERROR"]["score"] -= 90
    elif disabled_check:
        c_map["BTH_ADAPTER_DISABLED"]["score"] += 95
        c_map["BTH_ADAPTER_DISABLED"]["supports"].append("Controller is administratively disabled (Code 22).")
        c_map["BTH_ALL_HEALTHY"]["score"] -= 80
    elif driver_error_check:
        c_map["BTH_DRIVER_DEVICE_ERROR"]["score"] += 95
        c_map["BTH_DRIVER_DEVICE_ERROR"]["supports"].append(f"Controller reported hardware/driver error: {driver_error_check.error_code}.")
        c_map["BTH_ALL_HEALTHY"]["score"] -= 80

    # 3. Peripheral evaluation
    has_peripheral_errors = any(k.startswith("bth.peripheral.") and r.status == CheckStatus.WARNING for k, r in evidence_by_id.items())
    if has_peripheral_errors and operational_check and operational_check.status == CheckStatus.PASS:
        c_map["BTH_PERIPHERAL_ERROR"]["score"] += 80
        c_map["BTH_PERIPHERAL_ERROR"]["supports"].append("Core controller is operational, but paired peripheral reported device error.")

    # 4. Normalization
    findings: List[DiagnosisFinding] = []
    for c in candidates:
        raw_score = max(0.0, min(100.0, c["score"]))
        confidence = round(raw_score / 100.0, 2)

        if confidence >= 0.80:
            status = HypothesisStatus.CONFIRMED
        elif confidence >= 0.50:
            status = HypothesisStatus.LIKELY
        elif confidence >= 0.25:
            status = HypothesisStatus.POSSIBLE
        elif confidence <= 0.10:
            status = HypothesisStatus.RULED_OUT
        else:
            status = HypothesisStatus.INCONCLUSIVE

        findings.append(
            DiagnosisFinding(
                cause_id=c["cause_id"],
                title=c["title"],
                description=c["description"],
                confidence=confidence,
                status=status,
                supporting_evidence=c["supports"],
                refuting_evidence=c["refutes"],
                recommended_action=c["recommended_action"],
            )
        )

    findings.sort(key=lambda f: f.confidence, reverse=True)
    primary = findings[0] if findings and findings[0].confidence >= 0.50 else None

    if primary and primary.status == HypothesisStatus.CONFIRMED:
        summary = f"Confirmed root cause: {primary.title} (Confidence: {int(primary.confidence * 100)}%)."
    elif primary and primary.status == HypothesisStatus.LIKELY:
        summary = f"Probable root cause: {primary.title} (Confidence: {int(primary.confidence * 100)}%)."
    else:
        summary = "Diagnostic evidence is inconclusive; manual investigation required."

    return DiagnosisReport(
        domain="bluetooth",
        primary_finding=primary,
        all_findings=findings,
        evidence_count=len(evidence),
        is_conclusive=primary is not None and primary.status in (HypothesisStatus.CONFIRMED, HypothesisStatus.LIKELY),
        summary=summary,
    )


def evaluate_driver_hypotheses(evidence: List[DiagnosticResult]) -> DiagnosisReport:
    """Evaluate candidate root causes for driver and hardware device issues based on gathered evidence."""
    ev_map: Dict[str, DiagnosticResult] = {r.check_id: r for r in evidence}

    h_healthy = {"score": 50.0, "supports": [], "refutes": []}
    h_missing_drv = {"score": 0.0, "supports": [], "refutes": []}
    h_crashed_43 = {"score": 0.0, "supports": [], "refutes": []}
    h_disabled_22 = {"score": 0.0, "supports": [], "refutes": []}
    h_reboot_14 = {"score": 0.0, "supports": [], "refutes": []}

    # Analyze PnP error results
    code_28_devices = [r for r in evidence if r.check_id == "drv.device.code_28"]
    code_43_devices = [r for r in evidence if r.check_id == "drv.device.code_43"]
    code_22_devices = [r for r in evidence if r.check_id == "drv.device.code_22"]
    code_14_devices = [r for r in evidence if r.check_id == "drv.device.code_14"]
    all_healthy_res = ev_map.get("drv.pnp.all_healthy")

    if all_healthy_res and all_healthy_res.status == CheckStatus.PASS:
        h_healthy["score"] += 50.0
        h_healthy["supports"].append(all_healthy_res.observation)
        h_missing_drv["refutes"].append("No devices reporting error code 28")
        h_crashed_43["refutes"].append("No devices reporting error code 43")
        h_disabled_22["refutes"].append("No devices reporting error code 22")

    if code_28_devices:
        h_missing_drv["score"] += 95.0
        for dev in code_28_devices:
            h_missing_drv["supports"].append(dev.observation)
        h_healthy["score"] = 0.0
        h_healthy["refutes"].append(f"{len(code_28_devices)} device(s) missing drivers (Code 28)")

    if code_43_devices:
        h_crashed_43["score"] += 90.0
        for dev in code_43_devices:
            h_crashed_43["supports"].append(dev.observation)
        h_healthy["score"] = 0.0
        h_healthy["refutes"].append(f"{len(code_43_devices)} device(s) reported hardware failure (Code 43)")

    if code_22_devices:
        h_disabled_22["score"] += 90.0
        for dev in code_22_devices:
            h_disabled_22["supports"].append(dev.observation)
        h_healthy["score"] = 0.0
        h_healthy["refutes"].append(f"{len(code_22_devices)} device(s) disabled in Device Manager (Code 22)")

    if code_14_devices:
        h_reboot_14["score"] += 95.0
        for dev in code_14_devices:
            h_reboot_14["supports"].append(dev.observation)
        h_healthy["score"] = 0.0
        h_healthy["refutes"].append("Reboot pending for device driver initialization")

    # Display adapter correlation
    display_res = ev_map.get("drv.display.adapter_state")
    if display_res:
        if display_res.status == CheckStatus.PASS:
            h_healthy["supports"].append(display_res.observation)
        elif display_res.status == CheckStatus.FAIL:
            h_healthy["score"] = 0.0
            h_crashed_43["score"] += 20.0
            h_crashed_43["supports"].append(display_res.observation)

    candidates = [
        {
            "cause_id": "DRV_ALL_HEALTHY",
            "title": "All Hardware Devices and Drivers Operational",
            "description": "All connected PnP devices, display adapters, and USB controllers report normal operational status.",
            "score": h_healthy["score"],
            "supports": h_healthy["supports"],
            "refutes": h_healthy["refutes"],
            "recommended_action": "No repair needed; device manager and hardware subsystems are functioning normally.",
        },
        {
            "cause_id": "DRV_MISSING_DRIVERS",
            "title": "Missing Device Drivers (Code 28)",
            "description": "One or more hardware devices are connected but lack compatible drivers installed.",
            "score": h_missing_drv["score"],
            "supports": h_missing_drv["supports"],
            "refutes": h_missing_drv["refutes"],
            "recommended_action": "Run Windows Update or scan for hardware changes to provision missing drivers.",
        },
        {
            "cause_id": "DRV_DEVICE_CRASHED_CODE_43",
            "title": "Hardware Device Stopped Due to Error (Code 43)",
            "description": "A device reported an internal hardware failure, firmware timeout, or driver crash to Windows.",
            "score": h_crashed_43["score"],
            "supports": h_crashed_43["supports"],
            "refutes": h_crashed_43["refutes"],
            "recommended_action": "Rescan hardware devices via pnputil or restart the host controller.",
        },
        {
            "cause_id": "DRV_DEVICE_DISABLED_CODE_22",
            "title": "Hardware Device Disabled (Code 22)",
            "description": "One or more hardware devices are present but disabled in Windows Device Manager.",
            "score": h_disabled_22["score"],
            "supports": h_disabled_22["supports"],
            "refutes": h_disabled_22["refutes"],
            "recommended_action": "Re-enable the disabled device in Device Manager.",
        },
        {
            "cause_id": "DRV_REBOOT_REQUIRED_CODE_14",
            "title": "System Restart Required (Code 14)",
            "description": "Hardware device driver installation is complete but requires a system reboot to initialize.",
            "score": h_reboot_14["score"],
            "supports": h_reboot_14["supports"],
            "refutes": h_reboot_14["refutes"],
            "recommended_action": "Restart your computer to complete driver loading.",
        },
    ]

    findings: List[DiagnosisFinding] = []
    for c in candidates:
        raw_score = max(0.0, min(100.0, c["score"]))
        confidence = round(raw_score / 100.0, 2)

        if confidence >= 0.80:
            status = HypothesisStatus.CONFIRMED
        elif confidence >= 0.50:
            status = HypothesisStatus.LIKELY
        elif confidence >= 0.25:
            status = HypothesisStatus.POSSIBLE
        elif confidence <= 0.10:
            status = HypothesisStatus.RULED_OUT
        else:
            status = HypothesisStatus.INCONCLUSIVE

        findings.append(
            DiagnosisFinding(
                cause_id=c["cause_id"],
                title=c["title"],
                description=c["description"],
                confidence=confidence,
                status=status,
                supporting_evidence=c["supports"],
                refuting_evidence=c["refutes"],
                recommended_action=c["recommended_action"],
            )
        )

    findings.sort(key=lambda f: f.confidence, reverse=True)
    primary = findings[0] if findings and findings[0].confidence >= 0.50 else None

    if primary and primary.status == HypothesisStatus.CONFIRMED:
        summary = f"Confirmed root cause: {primary.title} (Confidence: {int(primary.confidence * 100)}%)."
    elif primary and primary.status == HypothesisStatus.LIKELY:
        summary = f"Probable root cause: {primary.title} (Confidence: {int(primary.confidence * 100)}%)."
    else:
        summary = "Diagnostic evidence is inconclusive; manual investigation required."

    return DiagnosisReport(
        domain="drivers",
        primary_finding=primary,
        all_findings=findings,
        evidence_count=len(evidence),
        is_conclusive=primary is not None and primary.status in (HypothesisStatus.CONFIRMED, HypothesisStatus.LIKELY),
        summary=summary,
    )

