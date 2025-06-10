import can
import time

# Choose the log file and format reader
log_filename = 'CANlog_VIN269.asc' # Or .blf, .log, .trc etc.
log_reader = can.LogReader(log_filename) # Automatically detects format for some types
# Or specify reader: log_reader = can.ASCReader(log_filename)

# Configure the CAN interface to send on
# Example using socketcan on Linux
bus = can.interface.Bus(channel='vcan0', bustype='socketcan', bitrate=500000)
# Example using PCAN
# bus = can.interface.Bus(channel='PCAN_USBBUS1', bustype='pcan', bitrate=500000)
# Example using Vector
# bus = can.interface.Bus(channel=0, bustype='vector', app_name='MyReplayScript', bitrate=500000)

print(f"Replaying {log_filename} on {bus.channel_info}")

try:
    start_time = time.monotonic()
    first_log_time = None

    for msg in log_reader:
        if first_log_time is None:
            first_log_time = msg.timestamp

        # Calculate time to wait based on message timestamps in the log
        # This maintains the relative timing between messages
        playback_time = start_time + (msg.timestamp - first_log_time)
        wait_time = playback_time - time.monotonic()

        if wait_time > 0:
            time.sleep(wait_time)

        # Create a new message object for sending to avoid modifying the logged one
        # (especially important if reusing the log_reader)
        send_msg = can.Message(
            arbitration_id=msg.arbitration_id,
            data=msg.data,
            is_extended_id=msg.is_extended_id,
            is_remote_frame=msg.is_remote_frame,
            is_error_frame=msg.is_error_frame
        )
        try:
          bus.send(send_msg)
          # print(f"Sent: {send_msg}") # Optional: print sent messages
        except can.CanError as e:
          print(f"Error sending message: {e}")


except KeyboardInterrupt:
    print("\nReplay stopped by user.")
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    bus.shutdown()
    log_reader.stop() # Close the file handle
    print("Bus shutdown and log file closed.")