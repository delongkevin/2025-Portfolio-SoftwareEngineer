-0-
These GELs are an adaptation of the internal GEL framework, modified for use/distribution to customers via the CSP.

To check all cores for a bare-metal system (no user code in ospi or sdcard) call the script:
	DO "~~~~/_J721S2_allcoretypes_connect.cmm"
This script initializes clocks using the Cortex-M4-0 the opens a new GUI per core. A modified version of this script can be used to start any subset of cores.  Simply comment out the cores not desired.

-1-
A platform level DDR test can be run by calling:
	DO "~~~~/_J721S2_ddr_test.cmm"

-2-
Scripts in the ./pdk_rtos_test/ directory allow for loading and running PDK FreeRTOS or TIRTOS examples.  These use TI-Firmware running on the TIFS-CortexM4

-3-
TRACE32 CORE names are as follows.

	; CM4 (2x1)  : J721S2-CM4-0 J721S2-CM4-1
	; A72 (1x2)  : J721S2 (core.assign 1 2)
	; CR5 (3x2)  : J721S2-CR5-MCU J721S2-CR5-MAIN0 J721S2-CR5-MAIN1 (core.assign 1 2)
	; C7x (2x1)  : J721S2-C71X (core.assign 1 2)

To allow for multi-core concurrent trace decode the tool’s side requires a "system.config CORE" option. The CORE # convention follows the above:
	CM4x: 1 2
	A72x: 3 4
	CR5x: 5 6 7 8 9 10
	C7x:  11 12

To select the 2nd C7x core the config file would use:
 	SYStem.CPU J721S2-C71X		; select C7x
 	SYStem.CONFIG CORE 12. 1.	; Core#12 on chip#1
	CORE.Assign 2.			; select 2nd C7x instance
NOTES: 
	Scripts which setup DDR only work after a power on reset and cannot be re-called as they depend on reset state.
	Bare metal scripts work with GP devices and HS-SE-WIR.  
	HS-SE-Firmware based devices will not allow M4 operations without a proper certificate with UID.
