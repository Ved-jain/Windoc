# WinDoc Commands & Codes Reference Guide

> **"Diagnostics and repairs for everyday people — no jargon, no hassle."**

WinDoc is designed around a simple principle: **regular users should not have to memorize complex parameters or fix procedures.** You only need two core commands to troubleshoot and fix your Windows computer:

1. **`windoc scan`** — See what is going on across all subsystems (and optionally fix with one keypress).
2. **`windoc fix`** — Automatically fix detected issues and independently verify the solution.

---

## 1. Quick Reference for Everyday Users (Zero Hassle)

| Command | What it Does | When to Use It |
| :--- | :--- | :--- |
| **`windoc scan`** | Scans all hardware and software subsystems in seconds. | Use when your computer, Wi-Fi, or Bluetooth feels slow, disconnected, or unresponsive. Prompts you to fix any detected issue automatically. |
| **`windoc fix`** | Finds what is broken, shows you the solution, and applies the fix after asking your permission. | Use when you just want your computer to work again without looking up manual fixes or procedure IDs. |
| **`windoc fix [domain]`** | Targets a specific subsystem: `network`, `bluetooth`, `drivers`, `update`, `system`, or `performance`. | Use when you only want to fix Wi-Fi, sound, drivers, or disk space without scanning the entire PC. Supports short aliases (`net`, `bth`, `drv`, `upd`, `sys`, `perf`). |
| **`windoc fix --yes`** | One-touch automatic fix mode (applies approved repairs immediately without asking). | Use for automated troubleshooting, script integration, or quick routine maintenance. |
| **`windoc diagnose <domain> --fix`** | Runs deep diagnostics on a single domain and immediately applies fixes if issues are detected. | Use when you want full diagnostic tables and instant repair for a single area (`windoc diagnose network --fix`). |
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

Recommended Fix: Flush DNS Resolver Cache
Expected Effect: Clears stale DNS entries and re-registers the Windows network resolver.

Apply fix for 'DNS Resolution Failure' now? [Y/n]: y

[OK] Fixed and Verified!
DNS resolution verified successfully after cache flush.
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
| `BTH_DRIVER_DEVICE_ERROR` | **Bluetooth Driver Crashed** | Bluetooth icon disappears or shows error code. | PnP query finds Bluetooth controller with non-zero error code. |
| `BTH_PERIPHERAL_ERROR` | **Peripheral Protocol Stalled** | Device is paired but will not connect or stream audio. | Bluetooth protocol services report errors or stalled connection states. |

### Drivers & Hardware Domain (`drv`)
| Cause Code | Plain-English Meaning | Common Symptom | How WinDoc Detects It |
| :--- | :--- | :--- | :--- |
| `DRV_ALL_HEALTHY` | **All Hardware Operational** | GPU, USB, and audio devices operate normally without warnings. | 0 connected PnP devices report Device Manager error codes; display adapter and USB controllers OK. |
| `DRV_MISSING_DRIVERS` | **Missing Hardware Driver** | Yellow exclamation mark in Device Manager, "PCI device" without driver. | PnP query finds connected device with ConfigManagerErrorCode `28` (Driver not installed). |
| `DRV_DEVICE_CRASHED_CODE_43` | **Hardware Device Error (Code 43)** | Device stopped functioning suddenly, GPU or controller driver crashed. | PnP query finds active device with ConfigManagerErrorCode `43` (Device reported problem). |
| `DRV_DEVICE_DISABLED_CODE_22` | **Hardware Device Disabled** | Hardware component is disabled by user or administrative policy. | PnP query finds active device with ConfigManagerErrorCode `22` (Device disabled). |
| `DRV_REBOOT_REQUIRED_CODE_14` | **Restart Required for Driver** | New driver installed, but device does not work until reboot. | PnP query finds active device with ConfigManagerErrorCode `14` (Restart required). |

### Windows Update Domain (`upd`)
| Cause Code | Plain-English Meaning | Common Symptom | How WinDoc Detects It |
| :--- | :--- | :--- | :--- |
| `UPD_ALL_HEALTHY` | **Windows Update Operational** | Updates download and install normally, update history intact. | Update background services (wuauserv, bits, cryptsvc) configured properly; cache verified. |
| `UPD_SERVICES_DISABLED` | **Update Services Disabled** | Error "We couldn't connect to the update service", updates fail to check. | Core update services configured with StartType `Disabled` (Code 4). |
| `UPD_REBOOT_REQUIRED` | **Restart Required for Updates** | Updates stuck at "Pending restart", new updates won't install. | Registry query confirms `RebootRequired` or CBS `RebootPending` flags are active. |

### System Integrity & Core Services (`sys`)
| Cause Code | Plain-English Meaning | Common Symptom | How WinDoc Detects It |
| :--- | :--- | :--- | :--- |
| `SYS_ALL_HEALTHY` | **System Files & Services Healthy** | Windows runs smoothly, no subsystem crashes. | Core OS services (RPC, DCOM, EventLog, WMI) running; WinSxS clean; no recent BSOD dumps. |
| `SYS_CORE_SERVICES_STOPPED` | **Core System Service Inactive** | System tools crash, WMI queries fail, event viewer broken. | Essential Windows services (EventLog, WMI, RPC) are stopped or disabled. |
| `SYS_COMPONENT_STORE_CORRUPT`| **Component Store Corrupted** | Windows features fail to install, SFC reports unfixable errors. | DISM CheckHealth or servicing registry confirms component store package corruption. |
| `SYS_RECENT_CRASHES` | **Recent Blue Screen (BSOD)** | PC restarted unexpectedly, blue screen crash recently occurred. | Crash minidump files found in `C:\Windows\Minidump` modified within last 7 days. |
| `SYS_SAFE_MODE_ACTIVE` | **Safe Mode Boot Detected** | Low resolution screen, audio and networking disabled. | CIM BootupState reports system booted in Safe or Diagnostic mode. |

### Performance & System Resources (`perf`)
| Cause Code | Plain-English Meaning | Common Symptom | How WinDoc Detects It |
| :--- | :--- | :--- | :--- |
| `PERF_ALL_HEALTHY` | **System Performance Optimal** | PC feels snappy, responsive, and balanced. | CPU load < 90%, RAM used < 92%, Drive C: free > 10 GB, uptime normal. |
| `PERF_DISK_LOW_SPACE` | **Low Disk Space on C:** | Windows "Low Disk Space" warning, updates fail to unpack. | System volume C: reports less than 10 GB or less than 10% free space remaining. |
| `PERF_MEMORY_EXHAUSTION` | **Severe Physical RAM Starvation** | Apps freeze, browser tabs crash, mouse stutters. | Total physical RAM consumption sustained above 92%, triggering severe disk paging. |
| `PERF_CPU_SATURATION` | **High CPU Utilization** | Fan running loud continuously, sluggish UI response. | Processor utilization measured above 90% sustained average across CPU cores. |
| `PERF_HIGH_UPTIME_DEGRADATION` | **Extended System Uptime** | Gradual slowdown over weeks of continuous sleep/wake. | Continuous Windows system uptime exceeds 30 days without a full reboot. |

---

## 4. Controlled Repair Procedures Reference

WinDoc only executes safe, allowlisted, non-destructive repair procedures. **Blind registry wiping and destructive resets are strictly prohibited.** Every actionable cause has a dedicated, verified repair:

| Repair Code | Procedure Name | Target Cause | Risk Level | Requires Admin? | What WinDoc Does & How It Verifies |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `net.flush_dns` | **Flush DNS Resolver Cache** | `NET_DNS_RESOLUTION_FAILED` | `LOW` | No | Clears local DNS cache (`ipconfig /flushdns`). **Verification:** Immediately re-resolves 3 global domains to confirm resolution is restored. |
| `net.renew_dhcp` | **Renew DHCP IP Lease** | `NET_DHCP_LEASE_FAILED` | `LOW` | No | Releases stale IP and requests fresh lease (`ipconfig /renew`). **Verification:** Queries network adapter to verify a non-APIPA IPv4 address was acquired. |
| `net.restart_adapter` | **Restart Network Adapter** | `NET_PHYSICAL_DISCONNECTED` | `MEDIUM` | **Yes** | Gracefully restarts the active network interface. **Verification:** Confirms adapter returns to `Up` state. |
| `net.reset_tcpip` | **Reset TCP/IP Stack & Winsock** | `NET_GATEWAY_UNREACHABLE` | `HIGH` | **Yes** | Resets Winsock catalog and IP routing stack. **Verification:** Confirms gateway connectivity. |
| `net.reset_proxy` | **Reset WinHTTP & User Proxy** | `NET_CAPTIVE_PORTAL_OR_PROXY`| `LOW` | **Yes** | Clears WinHTTP proxy and HKCU Internet Settings proxy. **Verification:** Verifies direct internet socket and HTTP connectivity. |
| `bth.restart_service` | **Restart Bluetooth Service** | `BTH_SERVICE_STOPPED` | `LOW` | **Yes** | Starts or restarts `bthserv`. **Verification:** Confirms service is actively `Running`. |
| `bth.enable_adapter` | **Enable Bluetooth Controller** | `BTH_ADAPTER_DISABLED` | `LOW` | **Yes** | Sends enable command to Bluetooth controller device. **Verification:** Queries Device Manager to ensure status returns to `OK`. |
| `bth.rescan_hardware` | **Rescan Bluetooth Hardware Tree** | `BTH_ADAPTER_MISSING` | `LOW` | **Yes** | Forces PnP device scan and restarts Bluetooth service. **Verification:** Queries for active Bluetooth radio adapter. |
| `bth.restart_device` | **Power-Cycle Bluetooth Controller** | `BTH_DRIVER_DEVICE_ERROR` | `LOW` | **Yes** | Disables and re-enables Bluetooth controller device. **Verification:** Re-checks PnP device tree for driver errors. |
| `bth.reset_stack` | **Reset Bluetooth Subsystem Services** | `BTH_PERIPHERAL_ERROR` | `LOW` | **Yes** | Restarts `bthserv` and `BthAvctpSvc`. **Verification:** Confirms protocol services running cleanly. |
| `drv.scan_missing_drivers` | **Scan Missing Drivers** | `DRV_MISSING_DRIVERS` | `LOW` | **Yes** | Re-scans PnP hardware tree and triggers Windows Update driver provisioning. **Verification:** Checks for remaining unprovisioned devices. |
| `drv.rescan_devices` | **Rescan Hardware Devices** | `DRV_DEVICE_CRASHED_CODE_43` | `LOW` | **Yes** | Re-enumerates PnP device tree (`pnputil /scan-devices`). **Verification:** Re-queries PnP devices to verify crashed devices recovered. |
| `drv.enable_device` | **Re-enable Disabled Hardware** | `DRV_DEVICE_DISABLED_CODE_22` | `LOW` | **Yes** | Sends enable command to disabled PnP device. **Verification:** Confirms device returned to `OK` state. |
| `drv.schedule_restart` | **Schedule Driver Setup Restart** | `DRV_REBOOT_REQUIRED_CODE_14` | `HIGH` | **Yes** | Schedules graceful 30-second restart for Code 14 driver finalization. **Verification:** Confirms scheduled restart flag. |
| `upd.reset_services` | **Reset Update Services** | `UPD_SERVICES_DISABLED` | `LOW` | **Yes** | Re-enables and starts `wuauserv`, `bits`, and `cryptsvc`. **Verification:** Queries Service Control Manager to confirm services are enabled. |
| `upd.reset_cache` | **Clear Update Download Cache** | `UPD_SERVICES_DISABLED` | `MEDIUM` | **Yes** | Purges corrupt `SoftwareDistribution\Download` cache and restarts services. **Verification:** Verifies update services healthy. |
| `upd.schedule_restart` | **Schedule Update Reboot** | `UPD_REBOOT_REQUIRED` | `HIGH` | **Yes** | Schedules graceful restart to finalize pending update installations. **Verification:** Checks reboot pending status. |
| `sys.repair_component_store` | **Repair Component Store (DISM)** | `SYS_COMPONENT_STORE_CORRUPT` | `MEDIUM` | **Yes** | Runs `dism.exe /Online /Cleanup-Image /RestoreHealth`. **Verification:** Confirms component store is restored to clean status. |
| `sys.restart_services` | **Restore System Services** | `SYS_CORE_SERVICES_STOPPED` | `LOW` | **Yes** | Re-enables and starts essential OS services (`EventLog`, `Winmgmt`, `RpcSs`). **Verification:** Confirms services are `Running`. |
| `sys.sfc_scan` | **System File Checker (SFC)** | `SYS_RECENT_CRASHES` | `MEDIUM` | **Yes** | Runs `sfc.exe /scannow` to replace corrupt OS files. **Verification:** Confirms integrity verified and no new minidumps. |
| `sys.exit_safe_mode` | **Exit Safe Mode** | `SYS_SAFE_MODE_ACTIVE` | `HIGH` | **Yes** | Clears `safeboot` flag from BCD to return to normal boot. **Verification:** Confirms BCD boot state configured normal. |
| `perf.clean_temp_files` | **Clean Temporary Cache Files** | `PERF_DISK_LOW_SPACE` | `LOW` | No | Safely purges temporary cache files in `%TEMP%`. **Verification:** Re-queries disk volume C: to verify freed space. |
| `perf.empty_recycle_bin` | **Empty Windows Recycle Bin** | `PERF_DISK_LOW_SPACE` | `LOW` | No | Purges deleted files residing in Windows Recycle Bin. **Verification:** Re-queries disk volume C: to verify reclaimed space. |
| `perf.clean_update_cache` | **Purge Stale Update Cache** | `PERF_DISK_LOW_SPACE` | `LOW` | **Yes** | Deletes old downloaded installation packages in `SoftwareDistribution`. **Verification:** Re-queries disk volume C:. |
| `perf.free_memory` | **Terminate High-RAM Consumers** | `PERF_MEMORY_EXHAUSTION` | `MEDIUM` | No | Safely terminates top RAM consumers on safe-to-kill allowlist. **Verification:** Re-queries physical RAM pressure. |
| `perf.free_cpu` | **Terminate High-CPU Workers** | `PERF_CPU_SATURATION` | `MEDIUM` | No | Safely terminates runaway allowlisted indexing/maintenance tasks. **Verification:** Re-checks CPU utilization. |
| `perf.schedule_restart` | **Graceful Reboot for Uptime** | `PERF_HIGH_UPTIME_DEGRADATION`| `HIGH` | **Yes** | Schedules 30-second restart with toast notification to flush kernel memory leaks. **Verification:** Confirms scheduled reboot. |

---

## 5. Advanced / Power User Commands

For IT technicians, software engineers, and power users who want targeted diagnostics or manual control:

```powershell
# Run diagnostics with optional immediate fix
windoc diagnose network --fix
windoc diagnose bluetooth --fix
windoc diagnose drivers --fix
windoc diagnose update --fix
windoc diagnose system --fix
windoc diagnose performance --fix

# List all 20+ approved repairs in the registry with safety metadata
windoc list-repairs

# Execute a specific repair directly by its code
windoc repair net.flush_dns
windoc repair bth.restart_service --yes

# Show system specs and environment details (OS, Python, elevation status)
windoc info

# Show all supported diagnostic domains
windoc list-domains

# Show WinDoc version
windoc --version
```

---

## 6. Security & Safety Guardrails

- **Consent First:** WinDoc will never modify your system without telling you what it plans to do and asking for your confirmation (unless `--yes` is explicitly passed).
- **Independent Post-Verification:** If a Windows command returns success (code 0) but the issue persists, WinDoc marks the repair as `VERIFICATION_FAILED` so you are never misled.
- **Least Privilege:** Diagnostics run in user-mode without asking for Administrator access. Administrator elevation is only prompted when a repair requires modifying system services or hardware adapters.
