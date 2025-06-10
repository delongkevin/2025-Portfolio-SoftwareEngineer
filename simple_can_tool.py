import can
import time
import threading
import argparse
import sys
import binascii

# --- Configuration ---
# Common interface names: pcan, vector, kvaser, serial, socketcan, virtual, slcan, ixxat
# Channels depend on the interface and hardware setup.
# Examples:
# PCAN: interface='pcan', channel='PCAN_USBBUS1'
# Vector: interface='vector', channel=0, app_name='CANalyzer' (or your registered app)
# Kvaser: interface='kvaser', channel=0
# Virtual: interface='virtual', channel='vcan0' (for testing without hardware)
# Serial: interface='serial', channel='COM3' (check device manager for port)

# --- Argument Parser ---
parser = argparse.ArgumentParser(description='Simple CAN Tool - Connects to CAN hardware, prints RX/TX.')
parser.add_argument('--interface', required=True, help='Interface type (e.g., pcan, vector, kvaser, virtual)')
parser.add_argument('--channel', required=True, help='Channel identifier (e.g., PCAN_USBBUS1, 0, vcan0, COM3)')
parser.add_argument('--baudrate', type=int, default=500000, help='CAN bus baud rate (e.g., 500000, 250000)')
parser.add_argument('--fd', action='store_true', help='Enable CAN FD mode')
parser.add_argument('--bitrate_switch', action='store_true', help='Enable bitrate switch for CAN FD') # Only if --fd is used
parser.add_argument('--data_baudrate', type=int, help='Data phase baud rate for CAN FD (e.g., 2000000)') # Only if --fd is used
parser.add_argument('--tx_id', type=str, help='Arbitration ID to send a test message (hex, e.g., 1A3)')
parser.add_argument('--tx_data', type=str, help='Data bytes to send (hex string, e.g., 01AABB)')
parser.add_argument('--extended_id', action='store_true', help='Use extended ID for TX message')

args = parser.parse_args()

# --- Global Variable for Bus ---
bus = None
stop_rx_thread_flag = threading.Event()

# --- RX Message Handling Thread ---
def receive_can_messages():
    """Receives and prints CAN messages."""
    print("RX Thread: Started. Waiting for messages...")
    try:
        while not stop_rx_thread_flag.is_set():
            # Use a timeout so the loop doesn't block indefinitely
            # making it easier to stop the thread later.
            msg = bus.recv(timeout=0.5)
            if msg is not None:
                timestamp = f"{msg.timestamp:.6f}"
                id_hex = f"{msg.arbitration_id:X}"
                id_str = f"ID: {id_hex.rjust(8 if msg.is_extended_id else 3)}"
                flags = []
                if msg.is_extended_id: flags.append("EXT")
                if msg.is_remote_frame: flags.append("RTR")
                if msg.is_error_frame: flags.append("ERR")
                if msg.is_fd: flags.append("FD")
                if msg.bitrate_switch: flags.append("BRS")
                if msg.error_state_indicator: flags.append("ESI")
                flags_str = f" Flags: [{' '.join(flags)}]" if flags else ""
                dlc_str = f" DLC: {msg.dlc}"
                data_str = f" Data: {msg.data.hex().upper()}" if msg.dlc > 0 else ""

                print(f"RX: Time: {timestamp} {id_str}{dlc_str}{flags_str}{data_str}")

            # Add a small sleep to prevent high CPU usage in some cases
            # time.sleep(0.001)

    except can.CanError as e:
        print(f"RX Thread: Error receiving message: {e}", file=sys.stderr)
    except Exception as e:
        print(f"RX Thread: An unexpected error occurred: {e}", file=sys.stderr)
    finally:
        print("RX Thread: Stopped.")


# --- Main Application Logic ---
def main():
    global bus
    rx_thread = None

    print(f"Attempting to connect:")
    print(f"  Interface: {args.interface}")
    print(f"  Channel:   {args.channel}")
    print(f"  Baudrate:  {args.baudrate}")
    if args.fd:
        print(f"  Mode:      CAN FD")
        if args.data_baudrate:
            print(f"  Data Rate: {args.data_baudrate}")
        if args.bitrate_switch:
            print(f"  BRS:       Enabled")

    # Construct configuration dictionary for python-can
    config = {
        'interface': args.interface,
        'channel': args.channel,
        'bitrate': args.baudrate,
        'fd': args.fd,
    }
    # Add FD specific parameters if FD is enabled
    if args.fd:
        if args.data_baudrate:
            config['data_bitrate'] = args.data_baudrate
        config['br_switch'] = args.bitrate_switch # Note: python-can uses 'br_switch'

    try:
        # Connect to the CAN bus
        bus = can.Bus(**config)
        print(f"\nSuccessfully connected to {bus.channel_info}")

        # Start the receiver thread
        rx_thread = threading.Thread(target=receive_can_messages, daemon=True)
        rx_thread.start()

        # Send an initial test message if specified
        if args.tx_id and args.tx_data:
            try:
                tx_arbitration_id = int(args.tx_id, 16)
                tx_payload = binascii.unhexlify(args.tx_data)
                message = can.Message(
                    arbitration_id=tx_arbitration_id,
                    data=tx_payload,
                    is_extended_id=args.extended_id,
                    is_fd=args.fd,  # Send as FD if FD mode is enabled
                    bitrate_switch=args.bitrate_switch if args.fd else False
                )
                bus.send(message)
                print(f"TX: Sent message -> ID: {args.tx_id.upper()}, Data: {args.tx_data.upper()}")
            except ValueError:
                print("TX Error: Invalid hex format for tx_id or tx_data.", file=sys.stderr)
            except binascii.Error:
                 print("TX Error: Odd-length hex string or non-hex characters in tx_data.", file=sys.stderr)
            except can.CanError as e:
                print(f"TX Error: Failed to send message: {e}", file=sys.stderr)

        # Keep the main thread alive, waiting for user input to exit
        print("\nBus connected. Printing received messages.")
        print("Press Ctrl+C to exit.")
        while True:
            time.sleep(1) # Keep main thread alive

    except can.CanError as e:
        print(f"\nError connecting to CAN bus: {e}", file=sys.stderr)
        print("Please check:")
        print("  - Hardware is connected.")
        print("  - Correct drivers are installed.")
        print("  - Interface name ('{args.interface}') is correct for your hardware and python-can.")
        print("  - Channel ('{args.channel}') is correct and not already in use.")
        print("  - Baudrate ('{args.baudrate}') matches the network.")
        if args.interface == 'vector':
             print("  - For Vector: Ensure hardware is configured in Vector Hardware Config and no other app (like CANoe/CANalyzer) is using the channel.")
        sys.exit(1) # Exit with error
    except ImportError as e:
         print(f"\nImport Error: {e}", file=sys.stderr)
         print(f"It seems the required library for the '{args.interface}' interface is not installed.")
         print(f"Try: pip install python-can[{args.interface}]") # e.g., pip install python-can[pcan] or python-can[vector]
         sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Cleanup
        print("\nShutting down...")
        stop_rx_thread_flag.set() # Signal the RX thread to stop
        if rx_thread:
            rx_thread.join(timeout=2) # Wait for the thread to finish
            if rx_thread.is_alive():
                print("Warning: RX thread did not terminate cleanly.")
        if bus:
            bus.shutdown()
            print("CAN bus shut down.")
        print("Exiting.")

# --- Entry Point ---
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Exiting.")
        # Ensure cleanup happens even with Ctrl+C in main loop
        stop_rx_thread_flag.set()
        if 'bus' in globals() and bus:
             try:
                 bus.shutdown()
                 print("CAN bus shut down.")
             except Exception as e:
                 print(f"Error during shutdown: {e}", file=sys.stderr)
        sys.exit(0)