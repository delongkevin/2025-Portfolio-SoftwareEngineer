# GM VIP Automation – Local Build Runbook & Jenkins Deployment Guide

This document explains how to **run the GM VIP Automation pipeline locally**
(without Jenkins) and how to **deploy it to a Jenkins CI/CD server** for
automated bench testing with e-mail reporting.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Repository layout](#3-repository-layout)
4. [Local Run (no Jenkins)](#4-local-run-no-jenkins)
   - 4.1 [Quick-start checklist](#41-quick-start-checklist)
   - 4.2 [Step-by-step walkthrough](#42-step-by-step-walkthrough)
   - 4.3 [Viewing the report](#43-viewing-the-report)
   - 4.4 [Sending the report by e-mail locally](#44-sending-the-report-by-e-mail-locally)
5. [Jenkins Pipeline Deployment](#5-jenkins-pipeline-deployment)
   - 5.1 [Jenkins prerequisites](#51-jenkins-prerequisites)
   - 5.2 [Agent node configuration](#52-agent-node-configuration)
   - 5.3 [Creating the pipeline job](#53-creating-the-pipeline-job)
   - 5.4 [First run](#54-first-run)
   - 5.5 [E-mail notifications in Jenkins](#55-e-mail-notifications-in-jenkins)
6. [E-mail Configuration Reference](#6-e-mail-configuration-reference)
7. [Script Reference](#7-script-reference)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Overview

GM VIP Automation supports **two execution modes** that share the same scripts
and produce identical HTML reports:

| Feature | Local run | Jenkins pipeline |
|---|---|---|
| CAPL validation | ✔ | ✔ |
| .NET T32 DLL build | ✔ | ✔ |
| Simulated test report | ✔ | ✔ |
| Bench tests (CANoe + T32) | with hardware | ✔ |
| E-mail report | via `email_report.py` + `.env` | via `email_report.py` + Jenkins credentials |
| HTML report viewer | open locally in browser | Jenkins HTML Publisher plugin |

The three Python scripts at the root of `GM_VIP_Automation` are **pure
standard-library** except for `Serial.py` (which needs `pyserial`) and
`email_report.py` (which is also standard-library only).  They run on any
Python 3.8 or later installation and produce the same output whether invoked
from a command prompt or from a Jenkins `bat` step.

---

## 2. Prerequisites

### 2.1 All machines (local and bench)

| Requirement | Why needed | Minimum version |
|---|---|---|
| **Python 3.8+** in `PATH` | All automation scripts | 3.8 |
| **Git** | Clone the repository | any |
| **Windows OS** | CANoe and Trace32 are Windows-only | Windows 10 / Server 2019 |

### 2.2 Validation-only machines (no bench hardware)

| Requirement | Notes |
|---|---|
| **dotnet SDK** in `PATH` | Needed to build the T32 .NET DLL (`Build-dotnetT32dll.ps1`) |

### 2.3 Bench machines (full test execution)

| Requirement | Notes |
|---|---|
| **CANoe 19+** – `CANoe64.exe` in `PATH` | Runs `.cfg` test configurations |
| **Trace32** – `t32rem.exe` in `PATH` | Debugger remote API |
| **Physical ECU** connected | For bench testing stages |
| **Tenma power supply** on a COM port | `Serial.py` / BVT stage |
| **`POWERSUPPLY_PORT`** env var set | e.g. `COM3` |

---

## 3. Repository layout

```
Portfolio-SoftwareEngineer/
└── OEM/
    └── GM_VIP_Automation/          ← AUTO_ROOT (all paths below are relative to here)
        ├── AutomationDependent/    CANoe CAPL libraries, T32 API DLL project
        ├── CAPL Testcases/         Per-feature CAPL test implementations
        ├── GM_VIP_RBS/             CANoe configuration (.cfg, .tse)
        ├── Testsuite_Environment/  Test suite XML definitions
        ├── Test Reports/           Generated XML & HTML reports (git-ignored)
        ├── misc/                   BVT T32 script, COM UI tool
        ├── config.cin              CAPL global constants
        ├── merge_reports.py        Merges XML reports → merged_report.html
        ├── simulate_tests.py       Validates CAPL definitions → simulated XML reports
        ├── validate_capl.py        Static CAPL syntax checker
        ├── email_report.py         Sends merged_report.html by e-mail
        ├── Serial.py               COM port power-supply control
        ├── serial_logging.ps1      PowerShell UART capture helper
        ├── requirements.txt        Python package dependencies (pyserial only)
        └── .env.example            Template for local e-mail credentials
```

---

## 4. Local Run (no Jenkins)

### 4.1 Quick-start checklist

```
[ ] Clone the repository
[ ] Verify Python 3.8+ is in PATH
[ ] cd OEM\GM_VIP_Automation
[ ] pip install -r requirements.txt
[ ] python validate_capl.py
[ ] python simulate_tests.py --out-dir "Test Reports\simulation"
[ ] python merge_reports.py --simulated --xml-dir "Test Reports\simulation"
          --out "Test Reports\merged_report.html"
[ ] Open Test Reports\merged_report.html in a browser
[ ] (optional) Configure .env and run python email_report.py
              --report "Test Reports\merged_report.html"
```

### 4.2 Step-by-step walkthrough

#### Step 1 – Clone and enter the project

```powershell
git clone https://github.com/<your-org>/Portfolio-SoftwareEngineer.git
cd Portfolio-SoftwareEngineer\OEM\GM_VIP_Automation
```

#### Step 2 – Install Python dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`pyserial` is the only third-party package.  All other scripts use the Python
standard library.

#### Step 3 – Validate CAPL files (static analysis)

```powershell
python validate_capl.py
```

This checks syntax, bracket balance, include chains, and testcase
definitions across all `.can` files.  Exit 0 = pass, exit 1 = errors found.

#### Step 4 – Build the .NET T32 DLL (optional – needed only for bench runs)

```powershell
powershell -ExecutionPolicy Bypass -File `
    "AutomationDependent\GenericLibraries\dotnetT32dll\Build-dotnetT32dll.ps1"
```

Skip this step if you only need the simulated report.

#### Step 5 – Run the simulation

```powershell
python simulate_tests.py `
    --root . `
    --out-dir "Test Reports\simulation"
```

The script discovers every `<capltestcase>` reference in the
`Testsuite_Environment\*.xml` files and checks whether the corresponding CAPL
`testcase` function exists in a `.can` file.  For each test suite it writes:

* `Test Reports\simulation\<suite>_simulated.xml` – CANoe schema (consumed by
  `merge_reports.py`)
* `Test Reports\simulation\junit\<suite>_junit.xml` – JUnit schema (consumed
  by Jenkins `junit()` step)
* `Test Reports\simulation\simulation_summary.txt` – human-readable summary

Exit code 0 = all references resolved, exit code 1 = one or more unresolved.

#### Step 6 – Generate the HTML report

```powershell
python merge_reports.py `
    --root . `
    --simulated `
    --xml-dir "Test Reports\simulation" `
    --out "Test Reports\merged_report.html"
```

| Flag | Purpose |
|---|---|
| `--root .` | Set `GM_VIP_Automation` root (defaults to the script's own directory) |
| `--simulated` | Adds a "Simulation Run" banner to the HTML |
| `--xml-dir` | Scan only a specific directory for XML files (e.g. simulation output) |
| `--out` | Output path for the HTML report |

After a real bench run (with CANoe writing to `Test Reports\**\*.xml`), omit
`--simulated` and `--xml-dir` to merge all real results instead:

```powershell
python merge_reports.py --root . --out "Test Reports\merged_report.html"
```

### 4.3 Viewing the report

Open the output file in any web browser:

```powershell
start "" "Test Reports\merged_report.html"
```

The report includes:

* Summary statistics cards (total / passed / failed / simulated)
* Progress bar
* Sidebar navigation per test module
* Expandable per-module result cards
* Step-level failure details
* Trace32 diagnostics section (when T32 reports are present)
* Print-friendly CSS

### 4.4 Sending the report by e-mail locally

#### 4.4.1 Configure credentials

```powershell
copy .env.example .env
notepad .env
```

Edit `.env` with your SMTP settings:

```ini
EMAIL_SMTP_HOST=smtp.office365.com
EMAIL_SMTP_PORT=587
EMAIL_SMTP_USER=gm-vip-automation@yourcompany.com
EMAIL_SMTP_PASS=your-password
EMAIL_USE_TLS=true
EMAIL_RECIPIENTS=lead@yourcompany.com,manager@yourcompany.com
EMAIL_FROM_NAME=GM VIP Automation
```

> **Security note:** `.env` is listed in `.gitignore` and will never be
> committed.  Do not paste credentials into any tracked file.

#### 4.4.2 Send the report

```powershell
python email_report.py --report "Test Reports\merged_report.html"
```

#### 4.4.3 Dry-run (validate config without sending)

```powershell
python email_report.py `
    --report "Test Reports\merged_report.html" `
    --dry-run
```

#### 4.4.4 Override recipients on the command line

```powershell
python email_report.py `
    --report "Test Reports\merged_report.html" `
    --recipients "alice@example.com,bob@example.com"
```

---

## 5. Jenkins Pipeline Deployment

### 5.1 Jenkins prerequisites

| Component | Notes |
|---|---|
| **Jenkins 2.387+** (LTS recommended) | |
| **Pipeline plugin** | Installed by default with Jenkins |
| **Git plugin** | For `checkout scm` |
| **HTML Publisher plugin** | Displays `merged_report.html` in the job UI |
| **JUnit plugin** | Shows simulated test results in the test trend graph |
| **Email Extension (emailext) plugin** | Sends rich HTML e-mail notifications |
| **Credentials plugin** | Stores SMTP password securely |
| **PowerShell plugin** | Executes `.ps1` scripts in pipeline steps |

Install all plugins via **Manage Jenkins → Manage Plugins → Available**.

### 5.2 Agent node configuration

#### windows-agent (validation builds – no bench hardware)

Any Windows PC running the Jenkins agent JAR with:

* Python 3.8+ in `PATH`
* dotnet SDK in `PATH`
* Git in `PATH`

Label the node **`windows-agent`** in **Manage Jenkins → Nodes**.

#### windows-bench (full bench runs)

Same as `windows-agent` PLUS:

* `CANoe64.exe` in `PATH` (add CANoe `Exec64` folder)
* `t32rem.exe` in `PATH` (add Lauterbach T32 install folder)
* Physical ECU connected
* Tenma power supply on a known COM port

Add the following **Environment variables** on the node
(**Manage Jenkins → Nodes → \<node\> → Configure → Environment variables**):

| Variable | Example value | Required |
|---|---|---|
| `POWERSUPPLY_PORT` | `COM3` | Yes (bench) |
| `FLASH_TOOL_EXE` | `nxp_flasher.exe` | When flash scripts are added |
| `BENCH_STAGING_DIR` | `C:\bench\GM_VIP_Automation` | Optional – stable path for CANoe |

Label the node **`windows-bench`**.

### 5.3 Creating the pipeline job

1. **New Item → Pipeline** – give the job a name, e.g.
   `GM-VIP-Automation`.

2. Under **Pipeline → Definition** choose **Pipeline script from SCM**.

3. Set:
   * **SCM**: Git
   * **Repository URL**: `https://github.com/<your-org>/Portfolio-SoftwareEngineer.git`
   * **Branch**: `*/main` (or your development branch)
   * **Script Path**: `Jenkinsfile`

4. Click **Save**.

#### 5.3.1 Store SMTP credentials

Store the SMTP password as a Jenkins **Secret text** credential so it is
never written in plain text:

1. **Manage Jenkins → Credentials → (global) → Add Credentials**
2. Kind: **Secret text**
3. ID: `gm-vip-smtp-pass`
4. Secret: your SMTP password

### 5.4 First run

1. Open the job and click **Build with Parameters**.
2. Leave `RUN_ON_BENCH = true` (or uncheck for a validation-only build).
3. Leave `SIMULATE = true` to generate a simulated report on `windows-agent`
   before the bench stages run.
4. Click **Build**.

After the pipeline completes:

* The **GM VIP Test Report** HTML link appears in the left sidebar of the
  build page (published by the HTML Publisher plugin).
* JUnit test trends appear in the build summary (simulation JUnit XML).
* All XML files are archived as build artifacts.

### 5.5 E-mail notifications in Jenkins

The Jenkinsfile is pre-wired to call `email_report.py` at the end of every
build.  To activate it:

#### 5.5.1 Set e-mail environment variables on each node

Add these variables under
**Manage Jenkins → Nodes → \<node\> → Environment variables**:

| Variable | Value |
|---|---|
| `EMAIL_SMTP_HOST` | `smtp.office365.com` |
| `EMAIL_SMTP_PORT` | `587` |
| `EMAIL_SMTP_USER` | `gm-vip-automation@yourcompany.com` |
| `EMAIL_USE_TLS` | `true` |
| `EMAIL_RECIPIENTS` | `lead@yourcompany.com,manager@yourcompany.com` |
| `EMAIL_FROM_NAME` | `GM VIP Automation` |

#### 5.5.2 Bind the SMTP password as a credential

In the Jenkinsfile the SMTP password is injected via `withCredentials`:

```groovy
withCredentials([string(credentialsId: 'gm-vip-smtp-pass',
                        variable: 'EMAIL_SMTP_PASS')]) {
    bat """
        python "%AUTO_ROOT%\\email_report.py" ^
               --report "%MERGED_REPORT%"
    """
}
```

This block already exists in the Jenkinsfile `post { always { ... } }`
section.  Replace `'gm-vip-smtp-pass'` with the credential ID you created in
step 5.3.1.

#### 5.5.3 Optional – also use emailext for direct Jenkins notifications

The Jenkinsfile `post { failure { ... } }` section contains a commented-out
`emailext` block.  Uncomment and configure it to receive plain-text failure
alerts in addition to the HTML report:

```groovy
failure {
    emailext(
        subject: "FAILED: GM VIP – ${env.JOB_NAME} #${env.BUILD_NUMBER}",
        body:    "Build URL: ${env.BUILD_URL}\n\nCheck the GM VIP Test Report for details.",
        to:      "your-team@yourcompany.com"
    )
}
```

---

## 6. E-mail Configuration Reference

The same environment variables are used by `email_report.py` whether it runs
locally (loaded from `.env`) or inside Jenkins (set on the agent node or
injected by `withCredentials`).

| Variable | Default | Description |
|---|---|---|
| `EMAIL_SMTP_HOST` | `localhost` | SMTP server hostname |
| `EMAIL_SMTP_PORT` | `587` | SMTP port |
| `EMAIL_SMTP_USER` | _(none)_ | Sender address / SMTP username |
| `EMAIL_SMTP_PASS` | _(none)_ | SMTP password |
| `EMAIL_USE_TLS` | `true` | Enable STARTTLS (port 587) |
| `EMAIL_USE_SSL` | `false` | Use implicit SSL (port 465) |
| `EMAIL_RECIPIENTS` | _(none)_ | Comma-separated recipient list |
| `EMAIL_FROM_NAME` | `GM VIP Automation` | Sender display name |
| `BUILD_NUMBER` | _(none)_ | Set automatically by Jenkins |
| `JOB_NAME` | _(none)_ | Set automatically by Jenkins |
| `BUILD_URL` | _(none)_ | Set automatically by Jenkins |

### Common SMTP settings

| Provider | Host | Port | TLS | SSL |
|---|---|---|---|---|
| Office 365 | `smtp.office365.com` | `587` | `true` | `false` |
| Gmail (App password) | `smtp.gmail.com` | `587` | `true` | `false` |
| Gmail (SSL) | `smtp.gmail.com` | `465` | `false` | `true` |
| Local relay | `localhost` | `25` | `false` | `false` |
| SendGrid | `smtp.sendgrid.net` | `587` | `true` | `false` |

---

## 7. Script Reference

### `validate_capl.py`

Static analysis of all `.can` CAPL files.

```
python validate_capl.py [--root <GM_VIP_Automation dir>]
```

Exit 0 = no issues; exit 1 = syntax / structural errors found.

### `simulate_tests.py`

Generates simulated XML and JUnit reports without bench hardware.

```
python simulate_tests.py [--root <dir>] [--out-dir <output dir>]
```

Outputs:
* `<out-dir>/<suite>_simulated.xml` – CANoe-schema report
* `<out-dir>/junit/<suite>_junit.xml` – JUnit report
* `<out-dir>/simulation_summary.txt` – human-readable summary

### `merge_reports.py`

Consolidates all XML reports into a single interactive HTML file.

```
python merge_reports.py [--root <dir>]
                        [--out <html file>]
                        [--simulated]
                        [--xml-dir <specific dir>]
```

Defaults: `--out "Test Reports/merged_report.html"`.

### `email_report.py`

Sends the HTML report by e-mail.

```
python email_report.py [--report <html file>]
                       [--subject "text"]
                       [--recipients "a@x.com,b@x.com"]
                       [--env-file <path to .env>]
                       [--dry-run]
```

Reads credentials from `.env` (local) or environment variables (Jenkins).

### `Serial.py`

COM port control for the Tenma programmable power supply.

```
python Serial.py --port COM3 --action on|off|status
```

### `serial_logging.ps1`

PowerShell script that opens a COM port and captures UART output to a log file.

```powershell
.\serial_logging.ps1 -Port COM4 -BaudRate 115200 -LogFile "Test Reports\uart.log"
```

---

## 8. Troubleshooting

### `GM_VIP_Automation` not found

```
FATAL: GM_VIP_Automation not found under <workspace>
```

Ensure you cloned the full repository and are running scripts from inside
`OEM\GM_VIP_Automation`, or pass `--root <path>` explicitly.

### `CANoe64.exe` not found in PATH

```
WARNING: CANoe64.exe not found in PATH
```

Add the CANoe `Exec64` folder to your Windows `PATH` environment variable, or
install CANoe on the bench agent.  Bench stages are skipped automatically on
`windows-agent` nodes that lack CANoe.

### `t32rem.exe` not found in PATH

Add the Lauterbach Trace32 install directory to `PATH`.

### Python `ModuleNotFoundError: pyserial`

```
python -m pip install -r requirements.txt
```

### SMTP connection refused (local)

* Verify `EMAIL_SMTP_HOST` and `EMAIL_SMTP_PORT` are correct.
* Check firewall / VPN rules for outbound SMTP.
* Use `--dry-run` first to validate config without connecting.

### SMTP authentication failed (Jenkins)

* Confirm the Jenkins credential ID matches the one in `withCredentials`.
* Verify the credential secret contains the correct password.
* For Office 365: ensure the sending mailbox has SMTP AUTH enabled in
  Exchange admin center.

### HTML report not appearing in Jenkins UI

* Confirm the **HTML Publisher plugin** is installed.
* Verify `allowMissing: true` is set in `publishHTML` (already set in the
  Jenkinsfile) so the stage does not fail when no bench run occurred.
* Check **Manage Jenkins → Configure System → Content Security Policy** if
  the report opens but has no styling.  The HTML Publisher plugin serves
  reports as static files; relax **only `style-src`** to allow the inline
  CSS written by `merge_reports.py`.  Do **not** add `script-src 'unsafe-inline'`
  globally – that would weaken Jenkins' XSS protections across the entire
  instance.  A safe starting point that enables inline styles without
  loosening script execution:
  ```
  sandbox allow-same-origin; default-src 'none'; img-src 'self'; style-src 'self' 'unsafe-inline';
  ```
  Apply the setting with the Jenkins Script Console
  (**Manage Jenkins → Script Console**):
  ```groovy
  System.setProperty(
      "hudson.model.DirectoryBrowserSupport.CSP",
      "sandbox allow-same-origin; default-src 'none'; img-src 'self'; style-src 'self' 'unsafe-inline';"
  )
  ```
  This setting resets on Jenkins restart; make it permanent by adding a
  `JAVA_OPTS` line to your Jenkins start-up configuration:
  ```
  -Dhudson.model.DirectoryBrowserSupport.CSP="sandbox allow-same-origin; default-src 'none'; img-src 'self'; style-src 'self' 'unsafe-inline';"
  ```
