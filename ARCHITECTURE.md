# WinDoc Architecture

## 1. Overview & Philosophy

WinDoc is an **evidence-driven Windows troubleshooting and repair tool**. Unlike naive repair scripts that run blind commands (e.g., `netsh winsock reset` or `ipconfig /flushdns` without checking if DNS is even the problem), WinDoc follows a diagnostic loop:

```
[Observe State] ──> [Generate Hypotheses] ──> [Select Discriminative Test] ──> [Update Beliefs]
        ▲                                                                              │
        └─────────────────────────── [Repeat if Inconclusive] ─────────────────────────┘
                                                       │
                                            [Diagnosis Supported]
                                                       │
                                                       ▼
                                     [Propose Safe Verified Repair]
```

---

## 2. Layered Design

```
+-------------------------------------------------------------+
|                     CLI Presentation Layer                  |
|                 (Typer + Rich terminal UI)                  |
+-------------------------------------------------------------+
                              |
+-------------------------------------------------------------+
|                      Diagnostic Engine                      |
|  - Manages investigation state                              |
|  - Evaluates competing hypotheses                           |
|  - Enforces investigation budgets and loop limits           |
+-------------------------------------------------------------+
              |                               |
+-----------------------------+ +-----------------------------+
|       Domain Checks         | |     Hypothesis Registry     |
| (Network, Bluetooth, etc.)  | | (Deterministic Rules)       |
+-----------------------------+ +-----------------------------+
              |
+-------------------------------------------------------------+
|                     Safe Command Runner                     |
|  - Process execution (`subprocess.run`, `shell=False`)      |
|  - Structured JSON parsing from PowerShell                  |
|  - Timeout enforcement and error handling                   |
+-------------------------------------------------------------+
                              |
+-------------------------------------------------------------+
|                  Controlled Repair Registry                 |
|  - Quarantined, verified actions                            |
|  - Precondition checks, explicit consent, post-verification |
+-------------------------------------------------------------+
```

---

## 3. Core Principles for Technical Defense

### Why Deterministic Logic Over Generative AI?
- **Zero Hallucination:** In system troubleshooting, suggesting a non-existent registry key or a destructive command can brick the operating system.
- **Predictability & Auditability:** Every decision must be traceable back to an exact test result and weighted rule.
- **Offline Reliability:** Core diagnostics should never fail because an external LLM API is down, rate-limited, or blocked by local network failures.

### Why PowerShell + Structured JSON?
- WinDoc prioritizes PowerShell cmdlets formatted with `| ConvertTo-Json` over scraping raw English console strings.
- String scraping is fragile across different Windows localizations (e.g., English vs German vs Japanese Windows). JSON gives typed, structured property dictionaries.

### Least Privilege & Safety
- **Read-Only First:** All diagnostic checks operate in read-only mode and do not require administrative privileges unless Windows explicitly locks down the interface.
- **No Arbitrary Commands:** WinDoc only executes allowlisted commands with predefined parameters.
- **Verified Repairs:** A repair is never considered successful just because the shell exit code was 0; the diagnostic check that originally failed must be re-run to confirm resolution.
