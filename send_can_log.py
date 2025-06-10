import can
import time
import argparse
import sys

def parse_log_line(line):
    """
    Parses a log line to extract CAN ID and data for Tx messages
    where the ID starts with "18 DA".
    Example line: "Tx: 18 DA 2E F2 02 10"
    Returns (arbitration_id, data, is_fd) or (None, None, None) if not a target message.
    """
    if line.startswith("Tx:"):
        parts = line.strip().split()
        # Expected format: Tx: ID1 ID2 ID3 ID4 DATA...
        # We are looking for ID1 = "18", ID2 = "DA"
        if len(parts) >= 5 and parts[1] == "18" and parts[2] == "DA":
            try:
                # The CAN ID is formed by the first four hex values after "Tx:"
                hex_id_parts = parts[1:5]
                arbitration_id_str = "".join(hex_id_parts)
                arbitration_id = int(arbitration_id_str, 16)

                # The rest are data bytes
                hex_data_parts = parts[5:]
                data = [int(p, 16) for p in hex_data_parts]

                # Determine if it's a CAN FD message (data length > 8)
                is_fd = len(data) > 8

                return arbitration_id, data, is_fd
            except ValueError as e:
                # Handle cases where conversion to int fails (e.g., non-hex characters)
                print(f"Warning: Could not parse hex values in line: {line.strip()}. Error: {e}")
                return None, None, None
            except IndexError:
                # Handle lines that look like they start correctly but are too short
                print(f"Warning: Malformed line (not enough parts for ID): {line.strip()}")
                return None, None, None
    return None, None, None

def main():
    parser = argparse.ArgumentParser(
        description="Reads a log file, extracts CAN messages with IDs starting with '18 DA XX XX', and sends them.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("logfile", help="Path to the debug log file.")
    parser.add_argument("--interface", default="socketcan",
                        help="CAN interface type (e.g., socketcan, pcan, vector, virtual, slcan, serial).\n"
                             "Default: socketcan")
    parser.add_argument("--channel", default="can0",
                        help="CAN channel (e.g., 'can0', 'PCAN_USBBUS1', 'COM3'). Default: 'can0'")
    parser.add_argument("--bitrate", type=int,
                        help="CAN bus bitrate (e.g., 500000). May be required for some interfaces.")
    parser.add_argument("--fd", action='store_true',
                        help="Enable CAN FD mode for the bus. Necessary if sending FD frames.")
    parser.add_argument("--data_bitrate", type=int,
                        help="CAN FD data phase bitrate (e.g., 2000000). Used if --fd is specified and supported by the interface.")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="Delay in seconds between sending messages. Default: 0.1s")

    args = parser.parse_args()

    print("--- CAN Message Sender from Log ---")
    print("\nIMPORTANT:")
    print("This script will send CAN messages onto the specified bus.")
    print("Sending incorrect messages to a real CAN bus, especially in a vehicle,")
    print("can have unintended and potentially dangerous consequences.")
    print("USE WITH EXTREME CAUTION AND AT YOUR OWN RISK.")
    print("Ensure you understand the messages being sent and their potential impact on the connected systems.")
    print("It is highly recommended to test this with a virtual CAN interface first (e.g., 'virtual' or 'vcan').")
    print("-------------------------------------\n")

    proceed = input("Do you understand the risks and wish to proceed? (yes/no): ")
    if proceed.lower() != 'yes':
        print("Operation cancelled by the user.")
        sys.exit(0)

    messages_to_send = []
    contains_fd_messages = False
    print(f"Reading messages from: {args.logfile}")
    try:
        with open(args.logfile, 'r') as f:
            for line_num, line in enumerate(f, 1):
                arbitration_id, data, is_fd_data = parse_log_line(line)
                if arbitration_id is not None and data is not None:
                    messages_to_send.append({
                        "id": arbitration_id,
                        "data": data,
                        "is_extended_id": True,  # Assuming 18DAXXXX is always an extended 29-bit ID
                        "is_fd": is_fd_data,
                        "line_num": line_num
                    })
                    if is_fd_data:
                        contains_fd_messages = True
    except FileNotFoundError:
        print(f"Error: Log file not found at {args.logfile}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading log file: {e}")
        sys.exit(1)

    if not messages_to_send:
        print("No 'Tx: 18 DA XX XX...' messages found in the log file.")
        sys.exit(0)

    print(f"\nFound {len(messages_to_send)} messages to send.")
    if contains_fd_messages:
        print("Log contains CAN FD messages. Ensure your CAN interface and configuration support CAN FD.")
        if not args.fd:
            print("Warning: CAN FD messages were found, but the --fd flag was not specified. The bus might not be initialized in FD mode.")

    bus_config = {'interface': args.interface, 'channel': args.channel}
    if args.bitrate:
        bus_config['bitrate'] = args.bitrate
    if args.fd:
        bus_config['fd'] = True
        if args.data_bitrate:
            bus_config['data_bitrate'] = args.data_bitrate
        else:
            # Many interfaces will default or derive this; some might error.
            print("Warning: --fd is set, but --data_bitrate is not specified. Using interface default if available.")
    
    # For some interfaces like Vector, additional parameters like app_name might be needed.
    # These would have to be added to bus_config if required for your specific hardware.
    # Example: if args.interface == 'vector': bus_config['app_name'] = 'MyApplication'

    print(f"\nAttempting to connect to CAN bus with config: {bus_config}")

    try:
        with can.interface.Bus(**bus_config) as bus:
            print(f"Successfully connected: {bus.channel_info}")
            print(f"Sending {len(messages_to_send)} messages with a delay of {args.delay}s between each...")

            for i, msg_info in enumerate(messages_to_send):
                message = can.Message(
                    arbitration_id=msg_info["id"],
                    data=msg_info["data"],
                    is_extended_id=msg_info["is_extended_id"],
                    is_fd=msg_info["is_fd"]
                    # bitrate_switch=False # Default, set to True if your FD messages use BRS
                )
                try:
                    bus.send(message)
                    data_str = ' '.join(f'{b:02X}' for b in message.data)
                    print(f"  Sent ({i+1}/{len(messages_to_send)} - Log Line {msg_info['line_num']}): "
                          f"ID=0x{message.arbitration_id:08X} DLC={message.dlc} FD={message.is_fd} Data=[{data_str}]")
                except can.CanError as e:
                    print(f"Error sending message (Log Line {msg_info['line_num']}): {message} - {e}")
                except Exception as e_send:
                    print(f"Unexpected error sending message (Log Line {msg_info['line_num']}): {message} - {e_send}")
                
                if i < len(messages_to_send) - 1: # Don't sleep after the last message
                    time.sleep(args.delay)
            
            print("\nAll targeted messages have been attempted.")

    except can.CanError as e:
        print(f"Error initializing or using CAN bus: {e}")
        print("Please ensure your CAN interface is correctly configured and connected.")
        print("Common interface setup examples:")
        print("  SocketCAN (Linux):")
        print("    sudo ip link set can0 down")
        print("    sudo ip link set can0 up type can bitrate 500000")
        print("    For CAN FD: sudo ip link set can0 up type can bitrate 500000 dbitrate 2000000 fd on")
        print("    Then run script with: --interface socketcan --channel can0")
        print("  PCAN (Windows/Linux):")
        print("    Ensure drivers are installed.")
        print("    Run script with: --interface pcan --channel PCAN_USBBUS1 --bitrate 500000")
        print("    For CAN FD: --fd --data_bitrate 2000000 (if your PCAN device supports it)")
        print("  Virtual (for testing without hardware):")
        print("    Run script with: --interface virtual --channel vcan0")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()