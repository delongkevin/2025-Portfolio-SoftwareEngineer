# GM VIP Automation – Test Case Technical Overview

**Project:** GM VIP (Vehicle Interface Platform) Software Quality Testing  
**Automation Framework:** CANalyzer / CANoe CAPL + Lauterbach Trace32 (T32) via GenericLibraries  
**Document Root:** `OEM/GM_VIP_Automation/`  
**Total Automated Test Cases:** 745 across 12 test modules  

---

## Table of Contents

1. [Automation Framework Architecture](#1-automation-framework-architecture)
2. [Test Execution Methodology](#2-test-execution-methodology)
3. [Module: BINVDM – Battery Non-Volatile Data Manager](#3-module-binvdm--battery-non-volatile-data-manager)
4. [Module: Battery Connection Status](#4-module-battery-connection-status)
5. [Module: CAN Driver (CNDD)](#5-module-can-driver-cndd)
6. [Module: Configuration Registers](#6-module-configuration-registers)
7. [Module: FPU – Floating Point Unit](#7-module-fpu--floating-point-unit)
8. [Module: HW_CRC – Hardware CRC Engine](#8-module-hw_crc--hardware-crc-engine)
9. [Module: Internal Bus](#9-module-internal-bus)
10. [Module: Lockstep (Dual-CPU)](#10-module-lockstep-dual-cpu)
11. [Module: OS Configuration](#11-module-os-configuration)
12. [Module: SWQT SP Device Support (Security Peripherals)](#12-module-swqt-sp-device-support-security-peripherals)
13. [Module: Stack Protection (SDL / Memory Protection)](#13-module-stack-protection-sdl--memory-protection)
14. [Module: Wake-Up Signal Management](#14-module-wake-up-signal-management)
15. [Cross-Cutting Coverage Analysis](#15-cross-cutting-coverage-analysis)
16. [Future Improvement Recommendations](#16-future-improvement-recommendations)

---

## 1. Automation Framework Architecture

### 1.1 Top-Level Directory Structure

```
OEM/GM_VIP_Automation/
├── CAPL Testcases/            # 12 subdirectories, one per software module
│   ├── BINVDM/
│   ├── Battery_Connection_Status/
│   ├── CAN/
│   ├── Config_registors/
│   ├── FPU/
│   ├── HW_CRC/
│   ├── Internal_bus/
│   ├── Lockstep/
│   ├── OS Config/
│   ├── SWQT_SP_Device_Support/
│   ├── Stack/
│   └── Wake_up/
├── AutomationDependent/       # Shared libraries (GenLib, T32 API, PowerSupply, etc.)
│   ├── GenericLibraries/      # CAPL control/support libs (T32, REPORT, COMMON)
│   ├── ProjectSpecific/       # Project-scoped include aggregator
│   ├── ProjectSupportLib/     # Additional project helpers
│   └── Docs/                  # Doxygen-generated HTML reference
├── Testsuite_Environment/     # CANoe .tse and XML test suite definitions
│   ├── GM_VIP_SWtest_Sanity.tse
│   ├── BINVDM.xml
│   ├── SWQT_Battery.xml
│   ├── SWQT_CAN.xml
│   ├── SWQT_Config_registor.xml
│   ├── SWQT_FPU.xml
│   ├── SWQT_HW_CRC.xml
│   ├── SWQT_InternalBus.xml
│   ├── SWQT_Test_cases_For_LockStep_Dual_CPU_Module.xml
│   ├── SWQT_Wakeup.xml
│   ├── OS_Testcase_Automation.xml
│   ├── Sanity.xml
│   └── Stack.xml
├── validate_capl.py           # Pre-deployment CAPL syntax / consistency checker
├── merge_reports.py           # Merges per-module XML test reports into one
├── Serial.py                  # UART log capture helper
├── serial_logging.ps1         # PowerShell UART capture for Windows benches
└── config.cin                 # Global configuration constants (paths, timeouts, etc.)
```

### 1.2 Core Libraries

| Library | File | Role |
|---------|------|------|
| **baseLib / COMMON** | `bcCOMMON.cin` | Defines `eActionEvaluation` enum (`Error=-1`, `NotOk=0`, `Ok=1`), shared types |
| **controlLib / T32** | `ccT32.cin` | T32 API constants – `cc_dwT32_MaxTimeout` (3 000 ms), `cc_dwT32_BP_HaltTimeout` (5 000 ms) |
| **testSupportLib / T32** | `tsT32.cin` | Action helpers (`A_DBGR_*`), evaluation helpers (`E_DBGR_*`), polling utilities (`waitForNotRunning`, `waitForRunning`) |
| **cREPORT** | `cREPORT.cin` | `TestCaseAddInfo()`, `vFctn_REPORTStepEvaluation()`, `vFctn_REPORTAddTestCaseInfo()` |
| **GenLib_Includes** | `GenLib_Includes` | Project-specific aggregator `#include` file used at the top of every `.can` |

### 1.3 Test Suite Registration (TSE / XML)

Each module has a matching XML file under `Testsuite_Environment/`. The XML files use `<capltestcase name="…"/>` elements to reference individual CAPL `testcase` functions by name. The `.tse` file (`GM_VIP_SWtest_Sanity.tse`) lists all XML files and the compiled `.cbf` binaries in synchronized CAPLLIBS and CBF blocks. A pre-deployment check (`validate_capl.py`) enforces that every `<capltestcase>` reference resolves to a definition in a `.can` file and validates bracket balance, include syntax, and declaration formatting.

---

## 2. Test Execution Methodology

All test cases share a common four-phase execution pattern:

### Phase 1 – Precondition Setup
```capl
A_DBGR_BreakpointDeleteAll();   // clear stale breakpoints
A_DBGR_R();                     // reset the target ECU
A_DBGR_Go() / A_DBGR_Go_Safe() / A_DBGR_RnGo();  // resume execution
```
`A_DBGR_Go_Safe()` includes an internal `waitForNotRunning` poll with `cc_dwT32_BP_HaltTimeout` (5 000 ms) before declaring the CPU halted. `A_DBGR_RnGo()` combines reset + go in a single call and is used when the test needs to observe the full startup sequence.

### Phase 2 – Stimulus / Configuration via Debugger
```capl
A_DBGR_BreakpointSet("FunctionName\\LineOffset");
A_DBGR_Go();
waitForNotRunning(20000);        // poll up to 20 s for halt
A_DBGR_VariableSet("var", "value");  // inject test vectors via watch window
```
Breakpoints are specified by `FunctionName\\LineOffset` (source-level) or `FunctionName` (entry point). After `A_DBGR_Go()`, `waitForNotRunning(timeout_ms)` polls the T32 state register in a loop of `pollInterval` = 100 ms increments until the CPU halts or the timeout expires.

### Phase 3 – Verification
```capl
E_DBGR_BreakpointCheckForHalt("FunctionName\\LineOffset");
E_DBGR_VariableCheck("variable", expectedValue, Equal|Greater|Less|NotEqual);
E_DBGR_CheckState(T32_State_Running);
```
Each `E_DBGR_*` call formats `chPassText` / `chFailText` strings, writes a debug trace via `writeDbgLevel`, and calls `vFctn_REPORTStepEvaluation()` to record a Pass/Fail step in the CANoe test report. The `eActionEvaluation` flag (`Ok=1` / `NotOk=0`) is set before the call.

### Phase 4 – Report & Clean-up
```capl
TestCaseAddInfo(chTestTitle, "TC_L30SW_QT_XXXXXXXX", chTestDescription);
TestStepAddActionExpected(chActionText, chExpectedText);
A_DBGR_BreakpointDeleteAll();
```
`TestCaseAddInfo` registers the test case title and requirement traceability ID with CANoe's test reporting engine. Individual steps are recorded with `TestStepAddActionExpected`. After each test case, all breakpoints are cleared to prevent interference with subsequent test cases.

### UART Log Verification (alternate path – Battery module)
Some test cases use a parallel verification method: a PowerShell script (`serial_logging.ps1`) or `Serial.py` captures UART output from the ECU, and the CAPL helper `iFcnt_READFILE_SearchKeywordInFile()` searches the captured log for an expected string pattern instead of using a T32 breakpoint watch. This is used where the software-under-test communicates results only through a serial trace port.

---

## 3. Module: BINVDM – Battery Non-Volatile Data Manager

**Source file:** `CAPL Testcases/BINVDM/BINVDM_Testcase_Automation.can`  
**XML suite:** `Testsuite_Environment/BINVDM.xml`  
**Test case count:** 43  
**Primary interfaces under test:** `GetHWIO_e_BatNonVltlReadSt()`, `ReadHWIO_h_BatNonVltl()`, `WriteHWIO_h_BatNonVltl()`, `EraseHWIO_h_BatNonVltl()`, `MemAcc_Read()`

### 3.1 Functional Coverage

The 43 test cases are organized into three operation families – **Read**, **Erase**, and **Write** – each exercised in both **Blocking** and **Non-Blocking** scheduling modes.

| Group | Scenarios Covered |
|-------|-------------------|
| **Read** (10 TCs) | Initial status (`BINVDM_READ_IDLE`), default status during in-progress, successful read completion (`BINVDM_READ_COMPLETE`), canceled read (`BINVDM_ERASE_CANCELED`), erased-location read (`BINVDM_READ_INPROGRESS`), memory error |
| **Erase** (18 TCs) | Initial status (`BINVDM_ERASE_IDLE`), erased segment verification (pass/fail), successful erase (`BINVDM_ERASE_COMPLETE`), memory error (`BINVDM_ERASE_MEM_ERROR`), error-during-erase (`BINVDM_ERASE_ERROR`), failed erase, canceled erase, default status through completion |
| **Write** (15 TCs) | Initial status (`BINVDM_WRITE_IDLE`), default status during in-progress, successful write (`BINVDM_WRITE_COMPLETE`), canceled write, memory error, error-during-write, failed write, data extend boundary |

### 3.2 Test Execution Pattern

Each BINVDM test case:
1. Resets the ECU and runs to a breakpoint inside `TestBinvdm_ReadGetStatus()` / `ReadHWIO_h_BatNonVltl()` / `WriteHWIO_h_BatNonVltl()` / `EraseHWIO_h_BatNonVltl()` in `test_binvdm_hwio.c`.
2. Sets or injects target variables (`binvdmSchmode`, `binvdmaddr`, `Nvmdataread`) to force the desired code path.
3. Steps through intermediate breakpoints inside `MemAcc_Read()` to observe `INPROGRESS` → final status transitions.
4. Calls `E_DBGR_VariableCheck("TstReadstatus", EXPECTED_ENUM_VALUE, Equal)` at each status transition.
5. Verifies the final idle/complete state at the end of the operation.

### 3.3 Coverage Gaps and Notes
- Non-blocking mode tests for the **Read canceled** and **Write extend** scenarios partially comment out `TestStepAddActionExpected` calls (`//TestStepAddActionExpected`), indicating steps that were deferred and need re-activation.
- The `BINVDM_READ_INPROGRESS` final-state check in erased-location tests stops before the idle transition – the idle-state assertion should be added for completeness.
- Multi-address boundary tests (address rollover, address alignment) are not yet covered.

---

## 4. Module: Battery Connection Status

**Source file:** `CAPL Testcases/Battery_Connection_Status/Battery_Automation.can`  
**XML suite:** `Testsuite_Environment/SWQT_Battery.xml`  
**Test case count:** 8  
**Primary interfaces under test:** `GetHWIO_b_BatConnectionStatus()`, `ClrHWIO_BatConnectionStatus()`

### 4.1 Functional Coverage

| Test Case | Scenario | Verification Method |
|-----------|----------|---------------------|
| TC1 | Battery connected, voltage in normal range → returns `0` | UART log search |
| TC2 | Battery disconnected → returns `1` (`BATTERY_DISCONNECT`) | UART log search |
| TC3 | `BATTERY_DISCONNECT` status retained until explicitly cleared by `ClrHWIO_BatConnectionStatus()` | UART log search |
| TC4 | System wakes up due to low voltage → returns `1` | UART log search |
| TC5 | System wakes up due to normal wakeup signal (not battery event) → returns `0` | UART log search |
| TC6 | `BATTERY_CONNECT` status retained unless disconnection event occurs | UART log search |
| TC7 | Controller reset when battery voltage is between 3.3 V and 4.5 V for 250 ms | UART log search |
| TC8 | Battery connection status updated to `1` (`BATTERY_DISCONNECT`) when voltage is 3.3–4.5 V | UART log search |

### 4.2 UART Log Verification Method

This module does **not** use T32 breakpoints. Instead:
1. `SysExec("powershell", "-ExecutionPolicy Bypass -File ./serial_logging.ps1", automation_root)` launches the UART capture script.
2. `A_GENERIC_SetTimeout(25000, …)` pauses the test for the ECU to produce output.
3. `iFcnt_READFILE_SearchKeywordInFile(teraterm, searchString, "string is present")` scans the TeraTerm log for a pattern such as `test_battconnstatus_hwio:battConnectionStatus = 0`.
4. Pass/Fail is reported with `testStepPass` / `testStepFail`.

### 4.3 Coverage Gaps and Notes
- Power-cycling is simulated through voltage injection; a programmable power supply (PowerSupply_libraries) is assumed available on the test bench.
- No negative test exists for `ClrHWIO_BatConnectionStatus()` being called while the battery is still physically disconnected.
- The voltage threshold transition from 4.5 V → normal range is not covered (only the 3.3–4.5 V window is tested).
- UART log file path (`teraterm`) is a global variable whose initialization must be verified in `config.cin` before execution.

---

## 5. Module: CAN Driver (CNDD)

**Source file:** `CAPL Testcases/CAN/CAN_Testcase_Automation.can`  
**XML suite:** `Testsuite_Environment/SWQT_CAN.xml`  
**Test case count:** 107  
**Primary interfaces under test:** `MngCNDD_CanRxInit()`, `CntrlCNDD_h_CanWrt()`, `SetCNDD_e_CanControllerMode()`, `SetCNDD_e_CanTrcvOpMode()`, `MngCNDD_CanTrcvInitialize()`, `MngCNDD_CanTrcvMain()`, `DsblCNDD_CanInterrupts()`, `EnblCNDD_CanInterrupts()`, `MngCNDD_CanMainMode()`, `MngCNDD_CanMainRead()`, `MngCNDD_CanMainBusOff()`, `GetCNDD_e_CanTrcvSpcfcFlts()`, `GetCNDD_Cnt_CanTxBufMax()`, `GetCNDD_Cnt_CanRxBufMax()`, `GetCNDD_Cnt_CanLoVoltEvnt()`  
**CAN controllers:** CANA (CAN2) and CANB (CAN8)

### 5.1 Functional Coverage

| Group | # TCs | Interfaces / Scenarios |
|-------|-------|------------------------|
| **RX Initialization** | 8 | Min/Max message length, Extended ID, Standard ID – for CAN2 and CAN8; dual-controller simultaneous init |
| **TX Transmission** | 7 | Min/max message length, successful transmission, disabled-channel blocking – for CAN2 and CAN8 |
| **TX Confirmation** | 2 | `SetCANR_e_CanIfTxConfirmation()` for standard ID on CAN2 and CAN8 |
| **Controller Mode** | 8 | Stop, Start, Sleep, WakeUp transitions for CAN2 and CAN8 |
| **Main Functions** | 4 | `MngCNDD_CanMainMode()` Stop/Start, `MngCNDD_CanMainRead()`, `MngCNDD_CanMainBusOff()` |
| **Transceiver Mode** | 8 | Normal, Sleep, Standby, Listen-Only – for CAN2 and CAN8 |
| **Transceiver Init** | 4 | Positive path for CAN2/CAN8; negative path with wrong CANID wakeup frame for CAN2/CAN8 |
| **Transceiver Main** | 2 | `MngCNDD_CanTrcvMain()` functionality for CAN2 and CAN8 |
| **Interrupt Control** | 5 | Disable/re-enable for CAN2, CAN8, and invalid channel |
| **Buffer Fill Level** | 12 | TX max, RX max, multiple message configurations (3, 64, 192 msgs; Full-CAN, Open SID/EID) |
| **Transceiver Faults** | 18 | TXD stuck-dominant, VSUP under-voltage, wake error, multiple faults, dominant bus state, partial networking, Vio/Vcc under-voltage, over-temperature, SPI error, selective-waker error, CRC EEPROM – for CAN2 and CAN8 |
| **Fault Reset** | 2 | Fault status cleared after controller reset (CAN2 and CAN8) |
| **Low-Voltage Events** | 6 | Counter read for single/multiple events, reset after controller reset – for CAN2 and CAN8 |
| **Stress** | 1 | WakeUp/Sleep cycling stress test |

### 5.2 Test Execution Pattern

CAN RX init tests inject configuration data directly into the CAN RX message structure (`VaCANR_CanRxMsgs[0].*`) via `A_DBGR_VariableSet()` before calling `MngCNDD_CanRxInit()`. TX tests inject payload and DLC fields and verify the transmit path through `CntrlCNDD_h_CanWrt()`. Transceiver fault tests set SPI register mirror variables to simulate fault conditions, then verify the bitmask returned by `GetCNDD_e_CanTrcvSpcfcFlts()`.

### 5.3 Coverage Gaps and Notes
- The `Flashing()` test case (L197) is a stub/placeholder – it contains no assertions and should either be completed or removed.
- Dual-controller simultaneous fault injection is not tested.
- CAN FD (extended data length) modes are not covered.
- Error-frame injection at the physical layer is not automated.

---

## 6. Module: Configuration Registers

**Source file:** `CAPL Testcases/Config_registors/Config_Registor.can`  
**XML suite:** `Testsuite_Environment/SWQT_Config_registor.xml`  
**Test case count:** 7  
**Primary interfaces under test:** `GetHWIO_e_FailedRegID()`, `GetHWIO_e_FailedBitID()`, `GetHWIO_b_FailedRegRecovSt()`, `PerfmHWIO_b_ConfigRegTest()`

### 6.1 Functional Coverage

| Test Case | Interface | Scenario |
|-----------|-----------|----------|
| TC1 | `GetHWIO_e_FailedRegID()` | `FAILED_REGISTER_ID` initialized to 0 on power-up reset |
| TC2 | `GetHWIO_e_FailedBitID()` | `FAILED_BIT_ID` initialized to 0 on power-up reset |
| TC3 | `GetHWIO_b_FailedRegRecovSt()` | `FAILED_REGISTER_RECOVER_STATUS` initialized to 0 on power-up reset |
| TC4 | `PerfmHWIO_b_ConfigRegTest()` | Returns `1` (test passed) when all registers pass the built-in test |
| TC5 | `GetHWIO_e_FailedRegID()` | Returns `0` when no registers failed in the last test cycle |
| TC6 | `GetHWIO_e_FailedBitID()` | Returns `0` when there is no last failed register |
| TC7 | `GetHWIO_b_FailedRegRecovSt()` | Returns `0` (success) for the last failed register recovery status |

### 6.2 Test Execution Pattern

All 7 test cases use a single-breakpoint approach: reset ECU, set a breakpoint at the function call site (`Test_ConfigRegister\\N`), run to halt, then call `E_DBGR_VariableCheck()` to verify the output variable. No variable injection is needed because these tests only verify the default/reset-state behavior.

### 6.3 Coverage Gaps and Notes
- Fault injection scenarios (artificially corrupting a register to force a non-zero `FailedRegID`) are not covered.
- `PerfmHWIO_b_ConfigRegTest()` returning `0` (test failed) is not tested.
- Recovery status for an intentionally injected failed register is not covered.

---

## 7. Module: FPU – Floating Point Unit

**Source file:** `CAPL Testcases/FPU/FPU_Testcase_Automation.can`  
**XML suite:** `Testsuite_Environment/SWQT_FPU.xml`  
**Test case count:** 198  
**Primary interfaces under test:** FPU exception handling in `Test_Float()`, MCU FPU configuration flags (`FPU_Core0`–`FPU_Core5`, `FP_CONFIG_INIHIBIT_RESET`)  
**CPU cores exercised:** Core0 through Core5 (6 cores)

### 7.1 Functional Coverage

The 198 test cases are structured as a matrix of **exception type × core × configuration mode**:

#### Exception Types (Phase 1 – `FP_CONFIG_INIHIBIT_RESET` not considered)
| Exception | # TCs per core | Variable Pairs Used |
|-----------|----------------|---------------------|
| Divide by Zero (3 scenarios) | 3 | `VeTEST_DivByZeroNum` / `VeTEST_PosZero`; negative zero; NaN operand |
| Round Towards Zero (3 scenarios) | 3 | `VeTEST_RTZ_Input` values with expected quantized result |
| Inexact Exception (2 scenarios) | 2 | Non-representable floating-point values |
| Underflow (3 scenarios) | 3 | Sub-normal numbers near `FLT_MIN` |
| Overflow (2 scenarios) | 2 | Values exceeding `FLT_MAX` |
| Invalid Operations – no reset (6 scenarios) | 6 | `0/0`, `NaN` arithmetic, multi-operand sequences |

**Sub-total Phase 1:** 19 TCs × 6 cores = **114 test cases**

#### Exception Types (Phase 2 – `FP_CONFIG_INIHIBIT_RESET` defined / not defined)
| Operation | # TCs per core × config | Description |
|-----------|------------------------|-------------|
| NaN operand (`x_NaN`) | 2 (defined/not-defined) | Quiet / signaling NaN input |
| `FLOAT` conversion | 2 | Integer-to-float near boundary |
| ADD, SUB, MUL, DIV, CMP | 2 each | Arithmetic with known invalid combinations |

**Sub-total Phase 2:** 7 operations × 2 configs × 6 cores = **84 test cases**

### 7.2 Test Execution Pattern

1. Set the per-core activation flag: `A_DBGR_VariableSet("FPU_Core0", "1")`.
2. Break at `Test_Float\\2` to confirm `coreId` matches the target core.
3. Inject operands (`VeTEST_DivByZeroNum`, `VeTEST_PosZero`, etc.) via `A_DBGR_VariableSet()`.
4. Step to the arithmetic line (`Test_Float\\10`) using a second breakpoint.
5. Verify the result: `E_DBGR_VariableCheck("VeTEST_DivideByPosZero", 340.28235E36, Equal)` for the saturation-to-max case.
6. Check that no unintended FPU exception flag is left set across test cases.

### 7.3 Coverage Gaps and Notes
- Tests assume IEEE 754 single-precision. Double-precision (`double`) exception behavior is not covered.
- Concurrent FPU exception triggering across multiple cores simultaneously is not tested.
- The FPU trap handler path (ISR-level exception) is not exercised directly; only the software-response path is verified.
- `FP_CONFIG_INIHIBIT_RESET` interaction with reset-then-execute sequences should be validated at startup, not only mid-execution.

---

## 8. Module: HW_CRC – Hardware CRC Engine

**Source file:** `CAPL Testcases/HW_CRC/HW_CRC.can`  
**XML suite:** `Testsuite_Environment/SWQT_HW_CRC.xml`  
**Test case count:** 56  
**Primary interfaces under test:** `GetHWIO_e_CalcCRC_St()`, `PerfmHWIO_h_CalcCRC()`, `GetHWIO_y_CRCSignature()`, hardware CRC32 / CRC16 / CRC8 calculation engines  
**CPU cores exercised:** Core0 through Core5

### 8.1 Functional Coverage

| Group | # TCs | Description |
|-------|-------|-------------|
| **Reset Initialization** | 6 | `v_crcSts_u8 == 0` after reset, all 6 cores; confirms `GetHWIO_e_CalcCRC_St()` returns idle on startup |
| **CRC32 In-Progress** | 6 | Breakpoint at start of CRC32 calculation; verifies `INPROGRESS` status returned while computation runs; Core0–Core5 |
| **CRC16 / CRC8 In-Progress** | 2 | Same in-progress check for CRC16 and CRC8 on Core0 |
| **CRC32 Signature Available** | 6 | `SignatureAvail` state verified after CRC32 completes; Core0–Core5 |
| **CRC16 / CRC8 Signature Available** | 2 | `SignatureAvail` state for CRC16 and CRC8 on Core0 |
| **Invalid Algorithm Failure** | 6 | Passing an unsupported algorithm enum value; `FAILURE` status expected; Core0–Core5 |
| **Invalid Start Address** | 8 | Address below or outside valid DFLASH range; `FAILURE` for CRC32 (all cores), CRC16, CRC8 on Core0 |
| **Invalid End Address** | 8 | Address above valid range; `FAILURE` for CRC32 (all cores), CRC16, CRC8 on Core0 |
| **New Request Before Signature Read (Pass)** | 1 | Submitting a new CRC request while previous result is available → passes |
| **New Request Before Signature Read (Fail)** | 1 | Scenario where the overwrite condition produces a failure |
| **CRC8 Failure Reporting** | 5 | `FAILURE` for CRC8 on Core1–Core5 |
| **CRC16 Failure Reporting** | 5 | `FAILURE` for CRC16 on Core1–Core5 |

### 8.2 Test Execution Pattern

1. Reset ECU; break at `TestApp_Core0_10ms_MainFunction\\45` (entry call to `Test_hwcrc_llsi()`).
2. Step into `Test_hwcrc_llsi\\22` to read `v_coreId_u8`; loop until the correct core executes.
3. Set breakpoints at specific internal CRC state-machine lines.
4. Read `v_crcSts_u8` (CRC status variable) and compare with `E_DBGR_VariableCheck()`.
5. For failure tests, inject invalid algorithm/address parameters via `A_DBGR_VariableSet()` before calling the CRC function.

### 8.3 Coverage Gaps and Notes
- CRC32 signature correctness (actual expected CRC value matching) is not checked — only the status flag is verified. Polynomial-level validation should be added.
- Multi-segment CRC (chained calculations across non-contiguous memory regions) is not tested.
- Performance benchmarking (CRC computation time across clock frequencies) is outside scope.
- CRC8 / CRC16 failure scenarios for Core1–Core5 are covered for failures only; the corresponding `SignatureAvail` and in-progress states for those cores are not individually tested.

---

## 9. Module: Internal Bus

**Source file:** `CAPL Testcases/Internal_bus/Internal_bus.can`  
**XML suite:** `Testsuite_Environment/SWQT_InternalBus.xml`  
**Test case count:** 25  
**Primary interfaces under test:** `GetHWIO_e_BusStatus()`, `GetHWIO_e_BusID()`, `GetHWIO_e_BusDeviceID()`  
**SPI buses monitored:** SPI_MCU_CAN2TCVR (Bus 1), SPI_MCU_CAN8TCVR (Bus 2), SPI_MCU_PMIC_TLF4D (Bus 3)

### 9.1 Functional Coverage

| Test Case | Interface | Scenario |
|-----------|-----------|----------|
| TC1 | `GetHWIO_e_BusStatus()` | Default value of `INTERNAL_BUS_STATUS` = 2 (`INDETERMINATE`) |
| TC2 | `GetHWIO_e_BusStatus()` | Returns correct value for all possible bus states |
| TC3 | `GetHWIO_e_BusStatus()` | Set to `INDETERMINATE` during reset initialization |
| TC4 | `GetHWIO_e_BusID()` | Default value of `BUS_ID` parameter |
| TC5 | `GetHWIO_e_BusStatus()` | Returns `0` (No Fault) when no faults are present |
| TC6 | `GetHWIO_e_BusStatus()` | Returns `1` (Fault) when a fault is injected |
| TC7 | `GetHWIO_e_BusID()` | Returns correct values for all bus IDs |
| TC8 | `GetHWIO_e_BusID()` | Set to `No_Bus_Network_Error` during reset initialization |
| TC9–TC12 | `GetHWIO_e_BusID()` | Bitwise OR for multiple simultaneous bus faults (4 scenarios: CAN2TCVR+CAN8TCVR, CAN2TCVR+PMIC, CAN8TCVR+PMIC, all three) |
| TC13 | `GetHWIO_e_BusDeviceID()` | Default value of `BUS_DEVICE_ID` parameter |
| TC14 | `GetHWIO_e_BusDeviceID()` | Returns correct values for all device IDs |
| TC15 | `GetHWIO_e_BusDeviceID()` | Set to `No_Device_Error` during reset initialization |
| TC16–TC19 | `GetHWIO_e_BusDeviceID()` | Bitwise OR for multiple simultaneous device faults (4 scenarios) |
| TC20–TC22 | `GetHWIO_e_BusID()` | Individual bus returns: PMIC_TLF4D (Bus 3), CAN8TCVR (Bus 2), CAN2TCVR (Bus 1) |
| TC23–TC25 | `GetHWIO_e_BusDeviceID()` | Individual device returns: PMIC_TLF4D (Device 3), CAN8TCVR (Device 2), CAN2TCVR (Device 1) |

### 9.2 Test Execution Pattern

Bus fault tests inject SPI fault condition flags into global status variables (e.g., `INTERNAL_BUS_STATUS`, `BUS_ID`) via `A_DBGR_VariableSet()` before stepping to the evaluation breakpoint inside `Test_GetHWIO_e_BusStatus()` or `Test_GetHWIO_e_BusID()`. The bitwise OR scenarios verify that the hardware-reported bitmask correctly accumulates multiple concurrent faults.

### 9.3 Coverage Gaps and Notes
- SPI bus recovery (fault cleared after re-initialization) is not tested.
- Intermittent fault detection (fault appearing then disappearing within a single poll cycle) is not covered.
- No test for `GetHWIO_e_BusID()` returning a value for Bus 0 (reserved / no bus).

---

## 10. Module: Lockstep (Dual-CPU)

**Source file:** `CAPL Testcases/Lockstep/SWQT_LockStep_Dual_CPU_Test_Cases_Scripts.can`  
**XML suite:** `Testsuite_Environment/SWQT_Test_cases_For_LockStep_Dual_CPU_Module.xml`  
**Test case count:** 9  
**Primary interfaces under test:** `GetHWIO_b_LockstepStN(BYTE cpuId)`, `GetHWIO_b_LockstepSt()`

### 10.1 Functional Coverage

| Test Case | CPU Core / cpuId | Expected Return | Description |
|-----------|-----------------|-----------------|-------------|
| TC1 | Core0 (cpuId=0) | `NO_FAILURE` (0) | Lockstep comparison passes on Core 0 |
| TC2 | Core1 (cpuId=1) | `NO_FAILURE` (0) | Lockstep comparison passes on Core 1 |
| TC3 | Core2 (cpuId=2) | `NO_FAILURE` (0) | Lockstep comparison passes on Core 2 |
| TC4 | Core3 (cpuId=3) | `NO_FAILURE` (0) | Lockstep comparison passes on Core 3 |
| TC5 | Core4 (cpuId=4) | `NO_FAILURE` (0) | Lockstep comparison passes on Core 4 |
| TC6 | Core5 (cpuId=5) | `NO_FAILURE` (0) | Lockstep comparison passes on Core 5 |
| TC7 | cpuId=6 (invalid) | `NO_LOCKSTEP` | Out-of-range CPU ID returns `NO_LOCKSTEP` |
| TC8 | cpuId=128 (invalid) | `NO_LOCKSTEP` | Boundary value CPU ID returns `NO_LOCKSTEP` |
| TC9 | cpuId=255 (invalid) | `NO_LOCKSTEP` | Maximum `BYTE` value CPU ID returns `NO_LOCKSTEP` |

### 10.2 Test Execution Pattern

Each test case follows a five-step breakpoint chain:
1. Break at `Test_GetHWIO_b_LockstepStN` (test harness entry).
2. Set `coreId` to the target value via `A_DBGR_VariableSet("coreId", "N")`.
3. Break at `GetHWIO_b_LockstepStN` (function entry) and verify `cpuId` matches.
4. Break at `GetHWIO_b_LockstepStN\\64` (`retval = NO_FAILURE` or `NO_LOCKSTEP` assignment).
5. Break at `GetHWIO_b_LockstepStN\\69` (`LockstepStatus[cpuId].lockstepStatus = retval`).
6. Break back at `Test_GetHWIO_b_LockstepStN\\6` and verify `retval == 0` (or `NO_LOCKSTEP`).

### 10.3 Coverage Gaps and Notes
- **Failure injection is entirely absent.** No test case forces a lockstep mismatch (CPU disagreement) to verify that `GetHWIO_b_LockstepStN()` returns a non-zero failure code.
- The `GetHWIO_b_LockstepSt()` (no `N` suffix – global status) is not independently tested.
- Startup-time lockstep initialization sequence is not verified.
- Post-failure recovery / re-synchronization path is not tested.

---

## 11. Module: OS Configuration

**Source file:** `CAPL Testcases/OS Config/OS_Testcase_Automation.can`  
**XML suite:** `Testsuite_Environment/OS_Testcase_Automation.xml`  
**Test case count:** 139  
**Primary interfaces under test:** `DisableHWIO_AllTasks()`, `EnableHWIO_AllTasks()`, `DsblHWIO_CPU()`, `GetHWIO_b_CPU_St()`, `GetHWIO_e_CPU()`, `TeHWIO_e_OS_Task()`, `GetHWIO_e_TaskID()`, `DsblHWIO_GM_TaskInits()`, `EnblHWIO_GM_TaskInits()`, `MngTSKR_e_PreTask()`, `MngTSKR_e_PostTask()`, `MngTSKR_TASKOS_TaskCPUx()`, `CntrlRBSR_Background()`, `CntrlRBSR_CntrlrReset()`, `MngTSKR_e_OS_Error()`, `DsblHWIO_Interrupt()`, `EnblHWIO_Interrupts()`, `GetHWIO_Pct_CPU_Utilization()`, `GetHWIO_Cnt_OS_TaskOverrun()`, `GetHWIO_t_OS_TaskExecution()`, `LockHWIO_Scheduler()`, `ReleaseHWIO_Scheduler()`, `PerfmHWIO_e_LockSemaphore()`, `PerfmHWIO_e_UnlockSemaphore()`, `GetHWIO_e_SemaphoreStatus()`  
**CPU cores exercised:** Core0 through Core5

### 11.1 Functional Coverage

| Group | # TCs | Scenarios |
|-------|-------|-----------|
| **Task Enable/Disable (All Tasks)** | 2 | `DisableHWIO_AllTasks()` and `EnableHWIO_AllTasks()` verified by monitoring 1000 ms task counters across all 6 cores |
| **CPU Disable** | 6 | `DsblHWIO_CPU()` for Core0–Core5; verifies the target core stops executing by checking its task counter halts |
| **CPU Status After Disable** | 6 | `GetHWIO_b_CPU_St()` returns disabled status for Core0–Core5 after `DsblHWIO_CPU()` |
| **Active CPU ID** | 6 | `GetHWIO_e_CPU()` returns correct active CPU ID (0–5) for each core |
| **Task ID** | 6 | `TeHWIO_e_OS_Task()` + `GetHWIO_e_TaskID()` returns correct task ID for Core0–Core5 |
| **Task Init Disable (GM TaskInits)** | 6 | `DsblHWIO_GM_TaskInits()` prohibits RTOS preemption; verified per core |
| **Task Init Enable (GM TaskInits)** | 6 | `EnblHWIO_GM_TaskInits()` re-enables RTOS preemption; verified per core |
| **Pre-Task Hook** | 6 | `MngTSKR_e_PreTask()` triggered before task invocation for Core0–Core5 |
| **Post-Task Hook** | 6 | `MngTSKR_e_PostTask()` triggered after task invocation for Core0–Core5 |
| **Task CPU Entry (1000 ms)** | 6 | `MngTSKR_TASKOS_TaskCPUx()` triggers normal 1000 ms task execution for Core0–Core5 |
| **Lockstep (OS module)** | 2 | `GetHWIO_b_LockstepStN()` called from OS context for CPU0 and CPU1 |
| **Background CPU Activity** | 6 | `CntrlRBSR_Background()` checks background CPU is active; Core0–Core5 |
| **OS Error Hook** | 6 | `MngTSKR_e_OS_Error()` triggered for OS error state; Core0–Core5 |
| **Controller Reset at Startup** | 6 | `CntrlRBSR_CntrlrReset()` called in startup; verified per core |
| **Interrupt Disable** | 6 | `DsblHWIO_Interrupt()` prohibits all interrupts for Core0–Core5 |
| **Interrupt Enable** | 6 | `EnblHWIO_Interrupts()` re-enables interrupts for Core0–Core5 |
| **CPU Utilization** | 6 | `GetHWIO_Pct_CPU_Utilization()` returns valid percentage for Core0–Core5 |
| **Task Overrun Count** | 6 | `GetHWIO_Cnt_OS_TaskOverrun()` increments after injected delay in task; Core0–Core5 |
| **Task Execution Time (1000 ms task)** | 6 | `GetHWIO_t_OS_TaskExecution()` returns measured time for Core0–Core5 |
| **Task Execution Time (2nd task type)** | 6 | Execution time for a different task period on Core0–Core5 |
| **Scheduler Lock/Unlock** | 6 | `LockHWIO_Scheduler()` + `ReleaseHWIO_Scheduler()` for Core0–Core5 |
| **Semaphore – All 31 IDs** | 6 | `PerfmHWIO_e_LockSemaphore()` + `PerfmHWIO_e_UnlockSemaphore()` for all 31 semaphore IDs on each core |
| **Semaphore – Cross-Core** | 3 | Lock in Core1, read from Core2; try locking same semaphore in Core2 (should fail); cross-core unlock validation |
| **Semaphore – Init Mode** | 6 | Lock/unlock in OS init mode for all 31 IDs, Core0–Core5 |
| **Semaphore – Shutdown Mode** | 6 | Lock/unlock in OS shutdown mode for all 31 IDs, Core0–Core5 |

### 11.2 Test Execution Pattern

Multi-core tests use task counter monitoring: after `A_DBGR_RnGo()`, the test reads a counter variable (`Task_CoreX_1000ms_Count`) via `A_DBGR_VariableRead()` and then calls `E_DBGR_VariableCheck("Task_CoreX_1000ms_Count", taskvalue, Greater)` after a wait – confirming that the counter advanced (core is running) or halted (core is disabled). Semaphore tests use a sequential set/read/verify pattern across 31 IDs in a loop.

### 11.3 Coverage Gaps and Notes
- Semaphore priority inversion and deadlock detection are not covered.
- `GetHWIO_Cnt_OS_TaskOverrun()` is tested only by injecting a delay; testing overrun due to genuine computational overload is not covered.
- Scheduler lock tests do not verify that tasks attempting to preempt during the lock period are correctly deferred.
- Cross-core interrupt signaling (IPI – Inter-Processor Interrupt) is not tested.

---

## 12. Module: SWQT SP Device Support (Security Peripherals)

**Source file:** `CAPL Testcases/SWQT_SP_Device_Support/SWQT_SP_Device_Support.can`  
**XML suite:** `Testsuite_Environment/Sanity.xml` (also referenced by `BINVDM.xml` / `OS_Testcase_Automation.xml` for sanity run)  
**Test case count:** 23  
**Primary interfaces under test:** `SetHWIO_h_CSM_RandomGenerate()`, `SetHWIO_h_CSM_RandomSeed()`, `SetHWIO_h_CSM_SymKeyWrap()`, `SetHWIO_h_CSM_SymKeyExtract()`, `SetHWIO_h_CSM_MACVerify()`, `SetHWIO_h_CSM_SymBlockDecrypt()`, `SetHWIO_h_CSM_SymEncrypt()`, `SetHWIO_h_CSM_SymDecrypt()`, `GetHWIO_e_SP_ErrorLLS()`  
**Hardware Security Module:** Crypto Service Manager (CSM) on the VIP ECU

### 12.1 Functional Coverage

| Test Case | CSM Operation | Steps Verified |
|-----------|---------------|----------------|
| To_Verify_CSM_Random_Number_Generate | Pseudo-random number generation (Start→Update→Finish) | `CsmConf_CsmJob_CsmJob_PseudoRandomNumberGenerate` job dispatched; `CSM_STATUS == 0` |
| To_Verify_CSM_Random_Seed_Start | Seed initialization start | Job dispatched; `CSM_STATUS == 0` |
| To_Verify_CSM_Random_Seed_Update | Seed data update | Seed data written; `CSM_STATUS == 0` |
| To_Verify_CSM_Random_Seed_Finish | Seed finalization | Seed finalized; `CSM_STATUS == 0` |
| To_Verify_CSM_Symmetric_Key_Wrapping_Start | Symmetric key wrap start | Key wrap job started; status OK |
| To_Verify_CSM_Symmetric_Key_Wrapping_Update | Key wrap data update | Wrapped key data accepted |
| To_Verify_CSM_Symmetric_Key_Wrapping_Finish | Key wrap completion | Wrapped key output verified |
| To_Verify_CSM_Symmetric_Key_Extract_Start | Key extraction start | `CSM_STATUS == 0` |
| To_Verify_CSM_Symmetric_Key_Extract_Update | Key extract data | Data fed into extraction |
| To_Verify_CSM_Symmetric_Key_Extract_Finish | Key extraction complete | Key extracted; status OK |
| To_Verify_Security_Peripheral_Error_LLS_NoError | `GetHWIO_e_SP_ErrorLLS()` | Returns `NoError` when no security peripheral fault active |
| To_Verify_CSM_MAC_Verify_Start | MAC verification start | Job started |
| To_Verify_CSM_MAC_Verify_Update | MAC data feed | MAC data written |
| To_Verify_CSM_MAC_Verify_Finish | MAC result | MAC result verified |
| To_Verify_CSM_Symmetric_Block_Decrypt_Start | Block decryption start | Job dispatched |
| To_Verify_CSM_Symmetric_Block_Decrypt_Update | Block data input | Data fed |
| To_Verify_CSM_Symmetric_Block_Decrypt_Finish | Decryption result | Plaintext verified |
| To_Verify_CSM_Symmetric_Encrypt_Start | Symmetric encryption start | Job dispatched |
| To_Verify_CSM_Symmetric_Encrypt_Update | Encryption data input | `CSM_STATUS == 0` |
| To_Verify_CSM_Symmetric_Encrypt_Finish | Encryption complete | Ciphertext output verified |
| To_Verify_CSM_Symmetric_Decrypt_Start | Symmetric decryption start | Job dispatched |
| To_Verify_CSM_Symmetric_Decrypt_Update | Decryption data input | `CSM_STATUS == 0` |
| To_Verify_CSM_Symmetric_Decrypt_Finish | Decryption result | Plaintext verified |

### 12.2 Test Execution Pattern

All 23 test cases use the same two-breakpoint pattern:
1. Break at `cybersec_features_test\\2` (selector entry), inject `CysecFeatureNum` to select the desired CSM operation.
2. Break at the specific `SetHWIO_h_CSM_*` call site and verify `CSM_STATUS == 0` (job accepted / completed successfully).

### 12.3 Coverage Gaps and Notes
- **Error path coverage is absent.** No test verifies CSM returns an error status (e.g., invalid key handle, wrong key size, authentication failure on MAC verify).
- Key slot provisioning and key lifecycle management are not tested.
- Asymmetric cryptographic operations (RSA, ECC) are not covered.
- `GetHWIO_e_SP_ErrorLLS()` is tested only for the `NoError` case; fault injection for security peripheral errors (e.g., IBUS error, SPI fault) is not covered.
- Re-entrancy and concurrent CSM job requests are not tested.

---

## 13. Module: Stack Protection (SDL / Memory Protection)

**Source file:** `CAPL Testcases/Stack/Stack_SWQT.can`  
**XML suite:** `Testsuite_Environment/Stack.xml`  
**Test case count:** 107  
**Primary interfaces under test:** `SMU_Init()`, `SDLAdaptor_init_ROM()`, `SDLAdaptor_run_RAM()`, `os_main()`, `MCU_Init()`, `MCU_InitClock()`, `Mcu_DistributePllClock()`, `GetHWIO_e_RstSrc()`, `GetHWIO_e_ROM_Flt()`, `GetHWIO_e_RAM_Flt()`, `GetHWIO_e_CacheRAM_Flt()`, `GetHWIO_y_ROM_AddressFailed()`, `GetHWIO_y_RAM_AddressFailed()`, `GetHWIO_y_CacheRAM_AddressFailed()`, `GetHWIO_Cnt_StackSize_RAM()`, `GetHWIO_Cnt_StackPeak_RAM()`, `ClrHWIO_ROM_Flt()`, `ClrHWIO_RAM_Flt()`, `ClrHWIO_CacheRAM_Flt()`, `SetHWIO_h_RAM_ECC_Init()`, `SetHWIO_b_WrtProtRAM_LckUnlck()`, `GetHWIO_b_WrtProtRAM_Flt()`, `GetHWIO_ptr_WrtProtRAM_FltAddr()`, `ClrHWIO_WrtProtRAM_Flt()`, `Tc4xMemProt_App_Init()`, `Tc4xMemProt_Init()`, `Tc4xMemProt_TrapHandler_Ifx()`, `TX4xMemProt_APP_Violation_CallBack()`, `Tc4xMemProt_Get_Error_StackOverflow()`, `Tc4xMemProt_Get_Error_StackUnderflow()`, `GetHWIO_e_StackProtSt()`, `hwio_reset_stack_request()`

### 13.1 Functional Coverage

| Group | # TCs | Scenarios |
|-------|-------|-----------|
| **Startup Interfaces** | 6 | `SMU_Init`, `SDLAdaptor_init_ROM`, `os_main`, `MCU_Init`, `MCU_InitClock`, `Mcu_DistributePllClock` – each verified by breakpointing at call site and definition side |
| **ROM Fault Detection** | 8 | `GetHWIO_e_ROM_Flt()`, `GetSDLAdaptor_e_ROM_Flt()`, `GetHWIO_y_ROM_AddressFailed()`, `GetSDLAdaptor_y_ROM_AddressFailed()`, `GetHWIO_y_ROM_InstAddressFailed()`, `GetSDLAdaptor_y_ROM_InstAddressFailed()`, `GetHWIO_y_ROM_FailedCPU_Specific()` (min/mid/max), `GetSDLAdaptor_y_ROM_FailedCPU_Specific()`, `ClrHWIO_ROM_Flt()`, `ClrSDLAdaptor_ROM_Flt()` |
| **RAM Fault Detection** | 12 | `SDLAdaptor_init_RAM`, `SDLAdaptor_run_RAM`, `GetHWIO_e_RAM_Flt()`, `GetSDLAdaptor_e_RAM_Flt()`, address failed (GetHWIO/GetSDL), instruction address failed, `ClrHWIO_RAM_Flt()`, `ClrSDLAdaptor_RAM_Flt()`, ECC init (min/mid/max), `GetSDLAdaptor_y_RAM_FailedCPU_Specific()`, `GetHWIO_y_RAM_FailedCPU_Specific()` (min/mid/max) |
| **Cache RAM Fault Detection** | 6 | `GetHWIO_e_CacheRAM_Flt()`, `GetSDLAdaptor_e_CacheRAM_Flt()`, address failed (GetHWIO/GetSDL), `ClrHWIO_CacheRAM_Flt()`, `ClrSDLAdaptor_CacheRAM_Flt()` |
| **Stack Size / Peak** | 2 | `GetHWIO_Cnt_StackSize_RAM()`, `GetHWIO_Cnt_StackPeak_RAM()` |
| **Write Protection** | 10 | Lock/Unlock (True/False), fault flag, fault address, fault instruction address, clear fault, `SetHWIO_y_WrtProtRAM_Update()` (min/mid/max), `SetHWIO_b_WrtProtRAM_LckUnlck()` |
| **Memory Protection Unit (MPU)** | 12 | `Tc4xMemProt_App_Init`, `Tc4xMemProt_Init`, `TrapHandler_Ifx`, `APP_Violation_CallBack`, stack overflow/underflow detection, write-protected access error, `SetProtectionContext` (unprotected/protected), `ClrHWIO_WrtProtRAM_Flt_Stack()` |
| **Stack Overflow / Underflow Status** | 20+ | `GetHWIO_e_StackProtSt()` for all 6 cores; overflow/underflow conditions, reset to `STACK_NO_ERROR`, combined conditions |
| **Timers and System Tick** | 6 | `os_main_Timers`, `Os_Entry_Task_Core0_10ms/100ms/250ms`, `GetHWIO_Cnt_SysTick()`, `GetHWIO_Cnt_SysTicksPerMicrosec()`, `GetHWIO_t_Current()`, `GetHWIO_e_CPU_timers()` |
| **CPU ID in Stack Context** | 1 | `GetHWIO_e_CPU()` returns correct active CPU ID |
| **Background RTOS** | 1 | `CntrlRBSR_Background()` called in stack context |
| **ISR Entry Points** | 2 | `Os_Entry_OS_SMUSafety_ISR1`, `Os_Entry_Task_Core0_10ms` verified at function entry |
| **Reset Source** | 1 | `GetHWIO_e_RstSrc()` verified at call site |

### 13.2 Test Execution Pattern

All stack module tests use the same dual-breakpoint verification:
1. Break at the **call site** (e.g., `App_MCALInit\\51`) to verify the calling code reaches the API.
2. Break at the **function definition entry** (e.g., `Smu_Init`) to verify the implementation is reached.
3. For fault/status interfaces, inject fault addresses or ECC error triggers via `A_DBGR_VariableSet()` and read back via `E_DBGR_VariableCheck()`.

### 13.3 Coverage Gaps and Notes
- Stack overflow / underflow tests for Core1–Core5 only check the status flag; the actual trapping and recovery ISR (`Tc4xMemProt_TrapHandler_Ifx`) is only tested on Core0.
- ECC multi-bit error (uncorrectable) injection is not tested; only single-bit correctable errors are inferred.
- `hwio_reset_stack_request()` is verified only for its call reachability, not for the resulting system reset behavior.
- Write-protection violation with the MPU active and real code attempting the write (live violation test) is not automated.

---

## 14. Module: Wake-Up Signal Management

**Source file:** `CAPL Testcases/Wake_up/Wakeup.can`  
**XML suite:** `Testsuite_Environment/SWQT_Wakeup.xml`  
**Test case count:** 23  
**Primary interfaces under test:** `GetHWIO_e_WakeupSigSt()`  
**Wakeup sources:** `wkupPwrOn` (battery), `wkupCanBusA` (CAN A bus), `wkupCanBusB` (CAN B bus), `wkupMultiple`

### 14.1 Functional Coverage

| # | Test Case (abbreviated) | Wakeup Source | Scenario |
|---|------------------------|---------------|----------|
| 1 | No wakeup events detected | None | `wakeEvent == 0` (idle) |
| 2 | Battery wakeup | `wkupPwrOn` | Normal startup wakeup |
| 3 | CAN A wakeup – scenario 1 | `wkupCanBusA` | LLSI CAN A bus wakeup (first configuration) |
| 4 | CAN A wakeup – scenario 2 | `wkupCanBusA` | LLSI CAN A bus wakeup (second frame type) |
| 5 | CAN A wakeup – scenario 3 | `wkupCanBusA` | LLSI CAN A bus wakeup (third variant) |
| 6 | CAN B wakeup (LLSI) | `wkupCanBusB` | LLSI function for CAN B wakeup detection |
| 7 | Battery wakeup during Init | `wkupPwrOn` | Battery wakeup event during system initialization |
| 8 | CAN A wakeup during Init | `wkupCanBusA` | CAN A wakeup during initialization phase |
| 9 | CAN B wakeup during Init | `wkupCanBusB` | CAN B wakeup during initialization phase |
| 10 | Battery wakeup during Shutdown | `wkupPwrOn` | Battery wakeup during shutdown sequence |
| 11 | Multiple wakeup events | `wkupMultiple` | CAN A + CAN B simultaneous wakeup |
| 12 | CAN A wakeup during Sleep | `wkupCanBusA` | Wakeup from sleep state via CAN A |
| 13 | CAN A – error frame counter overflow (CAN2) | `wkupCanBusA` | CAN2 error counter overflow triggers wakeup |
| 14 | CAN B – error frame counter overflow (CAN8) | `wkupCanBusB` | CAN8 error counter overflow triggers wakeup |
| 15 | CAN error overflow – CAN2 during Sleep | `GetHWIO_e_WakeupSigSt` | CAN2 error frame counter overflow in sleep state |
| 16 | CAN error overflow – CAN8 during Sleep | `GetHWIO_e_WakeupSigSt` | CAN8 error frame counter overflow in sleep state |
| 17 | CAN B wakeup during Sleep | `wkupCanBusB` | CAN B wakeup from sleep via CAN B bus |
| 18 | CAN2 error overflow during (2nd context) | `GetHWIO_e_WakeupSigSt` | Repeat scenario during different context |
| 19 | CAN8 error overflow during (2nd context) | `GetHWIO_e_WakeupSigSt` | Repeat scenario during different context |
| 20 | Invalid PN frame – no CAN A wakeup | None (negative) | Wrong partial-networking frame → no wakeup |
| 21 | Invalid PN frame – no CAN B wakeup | None (negative) | Wrong PN frame on CAN B → no wakeup |
| 22 | Stress – WakeUp/Sleep cycling | Multiple | Repeated wakeup/sleep transitions |
| 23 | Stress – Power Reset | Multiple | Repeated power reset cycling |

### 14.2 Test Execution Pattern

Wake-up tests use a single-breakpoint verification approach: break at `Test_GetHWIO_e_WakeupSigSt\\N` (the return point of the wrapper), verify `wakeEvent` matches the expected enum value. For CAN-triggered wakeup tests, the CAN wakeup frame is transmitted by the CANoe node layer (simulation) and the software reaction is read via T32.

### 14.3 Coverage Gaps and Notes
- LIN bus wakeup (if supported by the hardware) is not covered.
- Wakeup source reporting after a watchdog-triggered reset is not tested.
- Multiple simultaneous wakeup sources beyond CAN A + CAN B combined are not tested.
- PN frame validation (partial networking) is covered for the negative case but not for all valid frame permutations.

---

## 15. Cross-Cutting Coverage Analysis

### 15.1 Test Case Count Summary

| Module | File | Test Cases | Cores Covered |
|--------|------|-----------|---------------|
| BINVDM | `BINVDM_Testcase_Automation.can` | 43 | Core0 (single-core NVM) |
| Battery Connection Status | `Battery_Automation.can` | 8 | N/A (UART-based) |
| CAN Driver | `CAN_Testcase_Automation.can` | 107 | CAN2 (CANA), CAN8 (CANB) |
| Configuration Registers | `Config_Registor.can` | 7 | Core0 |
| FPU | `FPU_Testcase_Automation.can` | 198 | Core0–Core5 (all 6) |
| HW CRC | `HW_CRC.can` | 56 | Core0–Core5 (all 6) |
| Internal Bus | `Internal_bus.can` | 25 | N/A (SPI bus-level) |
| Lockstep | `SWQT_LockStep_Dual_CPU_Test_Cases_Scripts.can` | 9 | Core0–Core5 + invalid IDs |
| OS Configuration | `OS_Testcase_Automation.can` | 139 | Core0–Core5 (all 6) |
| SP Device Support | `SWQT_SP_Device_Support.can` | 23 | Core0 (security engine) |
| Stack Protection | `Stack_SWQT.can` | 107 | Core0–Core5 |
| Wake-Up | `Wakeup.can` | 23 | N/A (system-level) |
| **TOTAL** | | **745** | |

### 15.2 Requirement Traceability

Every test case calls `TestCaseAddInfo(chTestTitle, "TC_L30SW_QT_XXXXXXXX", chTestDescription)` where `TC_L30SW_QT_XXXXXXXX` is the requirement ID in the GM requirements management system. This creates a direct, machine-readable link between each automated test case and its originating requirement. The merge_reports.py script aggregates all per-module XML reports into a single consolidated report for delivery.

### 15.3 Verification Techniques Used

| Technique | Description | Modules Using It |
|-----------|-------------|-----------------|
| **Breakpoint + Variable Read** | Set T32 breakpoint, halt CPU, read variable via `E_DBGR_VariableCheck()` | All modules except Battery |
| **Variable Injection** | `A_DBGR_VariableSet()` to force code paths without hardware stimulus | BINVDM, CAN, Config Reg, FPU, HW_CRC, Internal Bus, Lockstep, OS, SP Device, Stack |
| **UART Log Search** | Capture UART trace, search for expected string pattern | Battery Connection Status |
| **Task Counter Monitoring** | Read/compare task execution counters to verify core alive/halted | OS Config |
| **State Polling** | `waitForNotRunning(20000)` polls T32 CPU state until halted or timeout | All modules |
| **Dual-Breakpoint Call/Definition** | Breakpoint at call site + breakpoint at function definition entry | Stack Protection |
| **Core Selection Loop** | Read core ID variable in a loop until target core executes | HW_CRC |
| **Stress / Repeat Cycling** | Repeated wakeup/sleep or power-reset sequences | CAN, Wake-up |

### 15.4 Coverage by Software Quality Dimension

| Quality Dimension | Coverage Level | Notes |
|-------------------|---------------|-------|
| **Interface coverage** | High | All public HWIO and CNDD interfaces have at least one test case |
| **Positive path** | High | Normal-operation paths are well covered across all modules |
| **Negative / error path** | Medium | Covered in BINVDM (canceled/error), CAN (invalid mode/channel), HW_CRC (invalid algorithm/address), Lockstep (invalid CPU ID), Wake-up (invalid PN frame); absent in SP Device Support and Config Registers |
| **Multi-core** | High | FPU, HW_CRC, OS Config, Stack, Lockstep all exercise Core0–Core5 independently |
| **Boundary value** | Medium | Present for FPU (min/max float), HW_CRC (invalid address), Stack (min/mid/max ECC/WrtProt), Lockstep (cpuId=255); not systematically applied to all modules |
| **Equivalence partitioning** | Medium | Blocking vs Non-Blocking mode in BINVDM; Normal/Sleep/Standby/Listen-Only in CAN transceiver; CRC8/CRC16/CRC32 types in HW_CRC |
| **Fault injection** | Low | Limited to variable-level injection via T32; hardware-level fault injection (power glitch, radiation) is out of scope |
| **Concurrency / race conditions** | Low | Cross-core semaphore tests exist in OS Config; otherwise concurrency scenarios are not systematically tested |
| **Recovery** | Low | Status-clear interfaces (ClrHWIO_*) are tested; full fault-to-recovery cycles are limited |

---

## 16. Future Improvement Recommendations

### 16.1 Short-Term (High Priority)

1. **Activate commented-out test steps** – Several test cases in BINVDM have `TestStepAddActionExpected` and final state assertion calls commented out. These should be re-activated and validated to complete the intended coverage.

2. **Add error-path tests for SP Device Support (CSM)** – The security module has zero negative test cases. Add tests for invalid job IDs, wrong key lengths, authentication failures on MAC verify, and SPI bus errors triggering `GetHWIO_e_SP_ErrorLLS()` with a non-zero error code.

3. **Add lockstep failure injection** – The Lockstep module only verifies the no-fault path. Add at least one test that injects a CPU mismatch (e.g., by patching a safety-relevant register differently on one core via T32) and verifies that `GetHWIO_b_LockstepStN()` returns a non-zero failure code.

4. **Complete Config Register fault injection** – Add test cases for `PerfmHWIO_b_ConfigRegTest()` returning `0` by corrupting a register value before the test function executes, and verify `GetHWIO_e_FailedRegID()` returns the correct ID.

5. **Verify BINVDM READ_IDLE transition** – The erased-location tests stop verifying status at `BINVDM_READ_INPROGRESS`. Add the final `BINVDM_READ_IDLE` assertion step to complete each scenario.

### 16.2 Medium-Term (Test Coverage Expansion)

6. **Extend HW_CRC to verify actual checksum values** – Current tests only check the CRC status flag (`INPROGRESS`, `SignatureAvail`, `FAILURE`). Add tests that compare the computed CRC signature against a known-good pre-calculated value for a fixed data block, confirming polynomial correctness.

7. **Add double-precision FPU tests** – The FPU module covers only single-precision (`float`). If the ECU software uses `double`, add test cases mirroring the existing ones for `double`-precision arithmetic.

8. **Add cross-module interaction tests** – Verify that FPU exceptions occurring in the middle of a CAN interrupt handler are correctly handled without corrupting CAN state, and that Lockstep faults are correctly reported while OS tasks are running.

9. **Battery negative-case expansion** – Add tests for: the voltage threshold crossing from 4.5 V back to normal, calling `ClrHWIO_BatConnectionStatus()` while still disconnected, and low-battery detection during active CAN communication.

10. **Parameterize multi-core tests** – Many tests for Core0–Core5 are copy-pasted with only the core index changed. Refactor into a `testfunction` with a core parameter, and use `for` loops to reduce maintenance overhead.

### 16.3 Long-Term (Architecture and Quality Infrastructure)

11. **Add automated requirements traceability report** – Extend `merge_reports.py` to produce a requirements coverage matrix that maps each `TC_L30SW_QT_*` ID to its test result, enabling gap analysis against the full requirements specification.

12. **Integrate static analysis in CI pipeline** – The existing `validate_capl.py` checks syntax and cross-file consistency. Extend it to check for: unhandled `E_DBGR_*` return values, test cases with no `TestCaseAddInfo` call, and test cases with `testStepPass` / `testStepFail` direct calls instead of the standard `E_DBGR_*` evaluation path.

13. **Add regression benchmarks for OS task execution times** – The OS Config module reads `GetHWIO_t_OS_TaskExecution()` but does not compare against a timing budget. Add upper-bound assertions (e.g., Core0 1000 ms task must complete in < X µs) to catch performance regressions.

14. **Hardware-in-the-loop (HiL) extension** – Transition Battery and Wake-up tests from UART log parsing to a direct T32 variable read approach, which eliminates dependency on TeraTerm log file timing and the PowerShell capture script.

15. **Semaphore priority inversion testing** – Add a multi-core scenario where a high-priority task on Core2 is blocked by a low-priority task on Core1 holding a semaphore, and verify the priority ceiling protocol responds correctly.

16. **Watchdog reset test coverage** – Add test cases that verify `GetHWIO_e_RstSrc()` returns the correct reset source code after a software-triggered watchdog reset, a hardware watchdog timeout, and a power-on reset, distinguishing all three cases.

---

*Document generated from source analysis of `OEM/GM_VIP_Automation/CAPL Testcases/` – 12 `.can` files, 745 test cases total.*  
*For questions on the automation framework contact the GenericLibraries maintainer (D2H7520_GENLIB). For test content questions contact the GM VIP software quality team.*
