import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

try:
    from can.io import BLFReader, ASCReader
    from can import Message as CanMessage
    PYTHON_CAN_AVAILABLE = True
except ImportError:
    PYTHON_CAN_AVAILABLE = False
    print("Warning: 'python-can' library not found. .asc and .blf file processing will not be available.")
    print("Please install it using: pip install python-can")

# --- Configuration ---
# Regex for .log files. This is an EXAMPLE and will LIKELY NEED MODIFICATION
# It expects lines like:
# [2023-10-27 10:00:00.123] Tx ID: 0x123 Data: 01 02 03 04
# [2023-10-27 10:00:00.456] Rx ID: 0x456 Data: AA BB CC
# It captures 'timestamp', 'direction' (Tx/Rx), 'id', and 'data'.
# If your .log has a different structure, you MUST adapt this regex.
# Ensure 'direction' capture group provides "Tx" or "Rx" (case-insensitive for processing).
# Other common fields you might want: 'channel', 'type', etc.
DEFAULT_LOG_PATTERN = r"\[(?P<timestamp>[^\]]+)\]\s+(?P<direction>Tx|Rx)\s+ID:\s*(?P<id>[0-9a-fA-Fx]+)\s+Data:\s*(?P<data>[0-9a-fA-F\s]+)"

# --- Helper Functions ---

def normalize_message_data(data_str):
    """ Helper to normalize data string (e.g., remove spaces, ensure consistent hex format) """
    if data_str is None:
        return ""
    return "".join(data_str.lower().split())

def parse_generic_log_file(filepath, pattern_str):
    """
    Parses a generic .log file using a regular expression.
    Yields a dictionary for each message.
    """
    messages = []
    try:
        pattern = re.compile(pattern_str, re.IGNORECASE)
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                match = pattern.search(line)
                if match:
                    msg_data = match.groupdict()
                    direction = msg_data.get('direction', 'Unknown').upper()
                    messages.append({
                        'timestamp': msg_data.get('timestamp', f'L{line_num}'),
                        'direction': 'Tx' if 'TX' in direction else ('Rx' if 'RX' in direction else 'Unknown'),
                        'id': msg_data.get('id', 'N/A'),
                        'data': normalize_message_data(msg_data.get('data')),
                        'raw_data': msg_data.get('data', ''), # Keep original spacing for display if needed
                        'type': 'LOG',
                        'source_line': line.strip(),
                        'line_num': line_num
                    })
                else:
                    # Optionally log lines that don't match
                    # print(f"Line {line_num} did not match pattern: {line.strip()}")
                    pass
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}")
    except Exception as e:
        print(f"Error parsing generic log file {filepath}: {e}")
    return messages

def parse_can_file(filepath, file_format):
    """
    Parses .asc or .blf CAN log files using python-can.
    Yields a dictionary for each message.
    """
    if not PYTHON_CAN_AVAILABLE:
        print(f"Cannot parse {file_format} files because python-can is not installed.")
        return []

    messages = []
    reader = None
    try:
        if file_format == 'asc':
            reader = ASCReader(filepath)
        elif file_format == 'blf':
            reader = BLFReader(filepath)
        else:
            print(f"Unsupported CAN format: {file_format}")
            return []

        for line_num, msg in enumerate(reader, 1):
            if isinstance(msg, CanMessage):
                messages.append({
                    'timestamp': f"{msg.timestamp:.6f}",
                    'direction': 'Rx' if msg.is_rx else 'Tx',
                    'id': f"{msg.arbitration_id:X}", # Hex format for ID
                    'data': msg.data.hex(), # Hex string for data
                    'raw_data': ' '.join(f"{b:02X}" for b in msg.data), # Spaced hex for display
                    'dlc': msg.dlc,
                    'is_extended_id': msg.is_extended_id,
                    'is_remote_frame': msg.is_remote_frame,
                    'is_error_frame': msg.is_error_frame,
                    'channel': msg.channel,
                    'type': 'CAN',
                    'source_line': str(msg), # Original python-can message string
                    'line_num': line_num
                })
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}")
    except Exception as e:
        print(f"Error parsing {file_format} file {filepath}: {e}")
    finally:
        if reader:
            reader.stop()
    return messages

def analyze_messages(messages):
    """
    Analyzes messages for uniqueness, repetitiveness, and Tx sequences.
    """
    if not messages:
        return {}, Counter(), []

    # Uniqueness and Repetitiveness
    # Define what makes a message unique (e.g., ID and Data for CAN)
    # For generic logs, you might include more fields or allow customization
    message_fingerprints = []
    for msg in messages:
        if msg['type'] == 'CAN':
            fingerprint = (msg['direction'], msg['id'], msg['data'])
        else: # LOG
            fingerprint = (msg['direction'], msg['id'], msg['data']) # Adjust for your log's key fields
        message_fingerprints.append(fingerprint)

    message_counts = Counter(message_fingerprints)

    unique_messages = []
    seen_fingerprints_for_unique_list = set()
    for i, msg in enumerate(messages):
        fingerprint = message_fingerprints[i]
        if fingerprint not in seen_fingerprints_for_unique_list:
            unique_messages.append(msg)
            seen_fingerprints_for_unique_list.add(fingerprint)

    # Consolidate Tx Sequences
    tx_sequences = []
    current_sequence = []
    for msg in messages:
        is_tx = msg['direction'] == 'Tx'

        if is_tx:
            if not current_sequence:
                current_sequence.append(msg)
            else:
                # For CAN, group by same ID. For LOG, just consecutive Tx.
                if msg['type'] == 'CAN' and current_sequence[-1]['id'] == msg['id']:
                    current_sequence.append(msg)
                elif msg['type'] == 'LOG': # Or other criteria for non-CAN Tx messages
                     current_sequence.append(msg)
                else: # New Tx sequence (different ID or non-CAN context)
                    if len(current_sequence) > 0: # Save previous sequence if it existed
                         tx_sequences.append(list(current_sequence))
                    current_sequence = [msg]
        else: # Not a Tx message (Rx or Unknown)
            if current_sequence:
                tx_sequences.append(list(current_sequence))
                current_sequence = []

    if current_sequence: # Add any trailing sequence
        tx_sequences.append(list(current_sequence))

    return unique_messages, message_counts, tx_sequences

def print_analysis_results(unique_messages, message_counts, tx_sequences, all_messages):
    """
    Prints the analysis results in a readable format.
    """
    print("\n--- Analysis Results ---")

    print(f"\nTotal messages parsed: {len(all_messages)}")

    print("\n--- Unique Messages (First Occurrence) ---")
    if unique_messages:
        for msg in unique_messages:
            print(f"[{msg['timestamp']}] {msg['direction']} ID: {msg.get('id', 'N/A')} Data: {msg.get('raw_data', msg.get('data', 'N/A'))} (Source Line: {msg['line_num']})")
    else:
        print("No unique messages found.")

    print("\n--- Message Repetitiveness (Counts) ---")
    if message_counts:
        # Sort by count descending for more relevant output
        for fingerprint, count in message_counts.most_common():
            direction, msg_id, data_payload = fingerprint
            # Find a sample message for display (raw_data might have better spacing)
            sample_msg = next((m for m in all_messages if m['direction'] == direction and m.get('id','N/A') == msg_id and m['data'] == data_payload), None)
            raw_data_display = sample_msg.get('raw_data', data_payload) if sample_msg else data_payload
            print(f"Count: {count} | {direction} ID: {msg_id} Data: {raw_data_display}")
    else:
        print("No message counts available.")

    print("\n--- Consolidated Tx Sequences ---")
    if tx_sequences:
        for i, seq in enumerate(tx_sequences):
            if not seq: continue
            print(f"\nTx Sequence {i+1} (ID: {seq[0].get('id', 'N/A')} - {len(seq)} messages):")
            # Option 1: Print all messages in the sequence
            for msg_idx, msg in enumerate(seq):
                 print(f"  [{msg['timestamp']}] Tx ID: {msg.get('id', 'N/A')} Data: {msg.get('raw_data', msg.get('data', 'N/A'))} (L: {msg['line_num']})")

            # Option 2: Summarize if messages in sequence are identical (beyond just ID)
            # This is a more advanced consolidation.
            # For now, we list them. If you want to count identical messages within a Tx sequence:
            # seq_counts = Counter((m['data'] for m in seq))
            # for data_payload, count in seq_counts.items():
            #     first_msg_for_payload = next(m for m in seq if m['data'] == data_payload)
            #     print(f"  ID: {first_msg_for_payload['id']} Data: {first_msg_for_payload['raw_data']} - Sent {count} times in this sequence (First at L: {first_msg_for_payload['line_num']})")

    else:
        print("No Tx sequences found or identified.")

# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(description="Parse Tx/Rx messages from log files (.log, .asc, .blf), "
                                                 "detect uniqueness and repetitiveness, and consolidate Tx sequences.")
    parser.add_argument("filepath", help="Path to the log file.")
    parser.add_argument("--filetype", choices=['log', 'asc', 'blf'],
                        help="Type of the log file. If not provided, attempts to infer from extension.")
    parser.add_argument("--log-pattern", default=DEFAULT_LOG_PATTERN,
                        help="Regex pattern for .log files. Ignored for .asc and .blf. "
                             "Ensure it has named capture groups: 'timestamp', 'direction', 'id', 'data'.")

    args = parser.parse_args()

    filepath = Path(args.filepath)
    filetype = args.filetype

    if not filepath.is_file():
        print(f"Error: File not found: {filepath}")
        return

    if not filetype:
        ext = filepath.suffix.lower()
        if ext == '.log':
            filetype = 'log'
        elif ext == '.asc':
            filetype = 'asc'
        elif ext == '.blf':
            filetype = 'blf'
        else:
            print(f"Error: Could not infer filetype from extension '{ext}'. Please