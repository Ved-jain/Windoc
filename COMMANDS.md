# WinDoc Commands & Codes Reference Guide

> **"Diagnostics and repairs for everyday people — no jargon, no hassle."**

WinDoc is designed around a simple principle: **regular users should not have to memorize complex parameters or fix procedures.** You only need two core commands to troubleshoot and fix your Windows computer:

1. **`windoc scan`** — See what is going on.
2. **`windoc fix`** — Automatically fix detected issues and verify the solution.

---

## 1. Quick Reference for Everyday Users (Zero Hassle)

| Command | What it Does | When to Use It |
| :--- | :--- | :--- |
| **`windoc scan`** | Scans all hardware and software subsystems in 5 seconds. | Use when your internet, Wi-Fi, or Bluetooth feels slow, disconnected, or unresponsive. |
| **`windoc fix`** | Finds what is broken, shows you the solution, and applies the fix after asking your permission. | Use when you just want your computer to work again without looking up manual fixes. |
| **`windoc fix --yes`** | One-touch automatic fix mode (applies approved repairs immediately without asking). | Use for automated troubleshooting or quick maintenance. |
| **`windoc activate`** | Registers WinDoc permanently in Windows. | Run once after downloading so you can use `windoc` from any terminal window without virtual environments. |

---

## 2. How the "Scan & Fix" Workflow Works

Instead of blindly running dangerous scripts, WinDoc acts like an expert technician:

```
[1. SCAN] ────► [2. DIAGNOSE] ────► [3. PROPOSE FIX] ────► [4. VERIFY]
Read system     Deterministic       Shows plain-English   Re-runs test
telemetry       root cause          recommendation and    to confirm problem
(Read-only)     identification      asks your consent     is actually fixed
```

### Example: Running `windoc fix`
```powershell
PS C:\> windoc fix

Problem Detected: DNS Resolution Failure
Websites cannot load because Windows cannot resolve domain names into IP addresses.

Recommended Fix: Flush and Reset DNS Cache
Expected Effect: Clears stale DNS entries and re-registers the Windows network resolver.

Apply fix for 'DNS Resolution Failure' now? [Y/n]: y

[OK] Fixed and Verified!
DNS resolution verified successfully. (Resolved 3/3 test domains).
```

---

## 3. Diagnostic Cause Codes Reference

Every issue WinDoc detects is assigned a transparent, deterministic **Root Cause Code**. Here is what each code means:

### Network Domain (`net`)
| Cause Code | Plain-English Meaning | Common Symptom | How WinDoc Detects It |
| :--- | :--- | :--- | :--- |
| `NET_ALL_HEALTHY` | **Network is Healthy** | Everything works. | Adapters UP, valid IPv4, gateway reachable, DNS resolves, TCP+HTTP verified. |
| `NET_DNS_RESOLUTION_FAILED` | **DNS Lookup Failed** | "Server IP address could not be found", web pages fail to load. | Adapters and gateway ping OK, but system cannot resolve `google.com` or `cloudflare.com`. |
| `NET_DHCP_LEASE_FAILED` | **Router IP Assignment Failed** | "No Internet, secured", yellow warning triangle on Wi-Fi icon. | Adapter assigned self-assigned APIPA address (`169.254.x.x`) because router DHCP server did not respond. |
| `NET_GATEWAY_UNREACHABLE` | **Router / Modem Not Responding** | Connected to Wi-Fi, but cannot reach any website or default gateway. | Default gateway IP is configured, but does not respond to ICMP ping echo requests. |
| `NET_PHYSICAL_DISCONNECTED` | **Cable Unplugged or Wi-Fi Off** | "Not connected - No connections are available". | All network interfaces report operational status `Down` or `Disconnected`. |
| `NET_CAPTIVE_PORTAL_OR_PROXY`| **Login Screen or Proxy Block** | Browser redirected to hotel/airport login page, or corporate proxy blocked. | TCP handshake to public IPs succeeds, but HTTP NCSI request returns redirect or 407 Proxy Auth. |

### Bluetooth Domain (`bth`)
| Cause Code | Plain-English Meaning | Common Symptom | How WinDoc Detects It |
| :--- | :--- | :--- | :--- |
| `BTH_ALL_HEALTHY` | **Bluetooth is Healthy** | Headphones, mice, and controllers connect properly. | Service `bthserv` is Running, adapter operational in Device Manager, paired devices responsive. |
| `BTH_SERVICE_STOPPED` | **Bluetooth Service Stopped** | Bluetooth toggle is missing from Windows Settings or Action Center. | Windows service `bthserv` status is `Stopped` or `Disabled`. |
| `BTH_ADAPTER_DISABLED` | **Bluetooth Hardware Disabled** | "Bluetooth is turned off", Device Manager shows down arrow. | Device Manager query returns ConfigManagerErrorCode `22` (Device Disabled). |
| `BTH_ADAPTER_MISSING` | **No Bluetooth Hardware Found** | System acts as if Bluetooth does not exist. | PnP hardware query finds 0 Bluetooth radio controllers. |

### Drivers & Hardware Domain (`drv`)
| Cause Code | Plain-English Meaning | Common Symptom | How WinDoc Detects It |
| :--- | :--- | :--- | :--- |
| `DRV_ALL_HEALTHY` | **All Hardware Operational** | GPU, USB, and audio devices operate normally without warnings. | 0 connected PnP devices report Device Manager error codes; display adapter and USB controllers OK. |
| `DRV_MISSING_DRIVERS` | **Missing Hardware Driver** | Yellow exclamation mark in Device Manager, "PCI device" without driver. | PnP query finds connected device with ConfigManagerErrorCode `28` (Driver not installed). |
| `DRV_DEVICE_CRASHED_CODE_43` | **Hardware Device Error (Code 43)** | Device stopped functioning suddenly, GPU or controller driver crashed. | PnP query finds active device with ConfigManagerErrorCode `43` (Device reported problem). |
| `DRV_DEVICE_DISABLED_CODE_22` | **Hardware Device Disabled** | Hardware component is disabled by user or administrative policy. | PnP query finds active device with ConfigManagerErrorCode `22` (Device disabled). |
| `DRV_REBOOT_REQUIRED_CODE_14` | **Restart Required for Driver** | New driver installed, but device does not work until reboot. | PnP query finds active device with ConfigManagerErrorCode `14` (Restart required). |

---

## 4. Controlled Repair Procedures Reference

WinDoc only executes safe, allowlisted, non-destructive repair procedures. **Blind registry wiping and destructive resets are strictly prohibited.**

| Repair Code | Procedure Name | Target Cause | Risk Level | Requires Admin? | What WinDoc Does & How It Verifies |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `net.flush_dns` | **Flush and Reset DNS Cache** | `NET_DNS_RESOLUTION_FAILED` | `LOW` | No | Clears local DNS cache (`ipconfig /flushdns`). **Verification:** Immediately re-resolves 3 global domains to confirm resolution is restored. |
| `net.renew_dhcp` | **Renew DHCP IP Lease** | `NET_DHCP_LEASE_FAILED` | `MEDIUM` | No | Releases stale IP and requests fresh lease (`ipconfig /renew`). **Verification:** Queries network adapter to verify a non-APIPA IPv4 address was acquired. |
| `net.restart_adapter` | **Restart Network Adapter** | `NET_GATEWAY_UNREACHABLE` | `MEDIUM` | **Yes** | Gracefully restarts the active network interface. **Verification:** Confirms adapter returns to `Up` state and gateway ping responds. |
| `bth.restart_service` | **Restart Bluetooth Service** | `BTH_SERVICE_STOPPED` | `LOW` | **Yes** | Starts or restarts `bthserv`. **Verification:** Queries Windows Service Control Manager to confirm service is actively `Running`. |
| `bth.enable_adapter` | **Re-enable Bluetooth Radio** | `BTH_ADAPTER_DISABLED` | `LOW` | **Yes** | Sends enable command to Bluetooth controller device. **Verification:** Queries Device Manager to ensure status returns to `OK` (ErrorCode 0). |
| `drv.rescan_devices` | **Rescan Hardware Devices** | `DRV_DEVICE_CRASHED_CODE_43` | `LOW` | **Yes** | Re-enumerates Plug and Play hardware tree (`pnputil /scan-devices`). **Verification:** Re-queries PnP devices to verify crashed devices recovered. |
| `drv.enable_device` | **Re-enable Disabled Hardware** | `DRV_DEVICE_DISABLED_CODE_22` | `LOW` | **Yes** | Sends enable command to disabled PnP device. **Verification:** Queries Device Manager to confirm device returned to `OK` state. |

---

## 5. Advanced / Power User Commands

For IT technicians, software engineers, and power users who want targeted diagnostics or manual control:

```powershell
# Run diagnostics only for network
windoc diagnose network

# Run diagnostics only for Bluetooth
windoc diagnose bluetooth

# Run diagnostics only for hardware devices and drivers
windoc diagnose drivers

# List all approved repairs in the registry with safety metadata
windoc list-repairs

# Execute a specific repair directly by its code
windoc repair net.flush_dns
windoc repair bth.restart_service --yes

# Show system specs and environment details (OS, Python, elevation status)
windoc info

# Show all supported and upcoming diagnostic domains
windoc list-domains

# Show WinDoc version
windoc --version
```

---

## 6. Security & Safety Guardrails

- **Consent First:** WinDoc will never modify your system without telling you what it plans to do and asking for your confirmation (unless `--yes` is explicitly passed).
- **Independent Post-Verification:** If a Windows command returns success (code 0) but the internet is still broken, WinDoc marks the repair as `VERIFICATION_FAILED` so you are never misled.
- **Least Privilege:** Diagnostics run in user-mode without asking for Administrator access. Administrator elevation is only prompted when a repair requires modifying system services or hardware adapters.
