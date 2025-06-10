import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import time
import json
import csv
import can

class CANLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CAN Logger (python-can)")
        self.running = False
        self.log_format = tk.StringVar(value="txt")
        self.direction = tk.StringVar(value="rx")
        self.filter_ids = set()
        self.create_widgets()

    def create_widgets(self):
        frame = tk.Frame(self.root, padx=10, pady=10)
        frame.pack()

        # Direction
        tk.Label(frame, text="Log Direction:").grid(row=0, column=0, sticky='w')
        tk.Radiobutton(frame, text="RX", variable=self.direction, value="rx").grid(row=0, column=1)
        tk.Radiobutton(frame, text="TX", variable=self.direction, value="tx").grid(row=0, column=2)
        tk.Radiobutton(frame, text="Both", variable=self.direction, value="both").grid(row=0, column=3)

        # Format
        tk.Label(frame, text="Log Format:").grid(row=1, column=0, sticky='w')
        formats = [("TXT", "txt"), ("CSV", "csv"), ("JSON", "json"), ("ASC", "asc")]
        for i, (text, value) in enumerate(formats):
            tk.Radiobutton(frame, text=text, variable=self.log_format, value=value).grid(row=1, column=1+i)

        # Filter
        tk.Label(frame, text="CAN ID Filter (e.g. 123,200-210):").grid(row=2, column=0, sticky='w')
        self.filter_entry = tk.Entry(frame, width=40)
        self.filter_entry.grid(row=2, column=1, columnspan=4, sticky='w')

        # Buttons
        self.start_btn = tk.Button(frame, text="Start Logging", command=self.start_logging)
        self.start_btn.grid(row=3, column=0, pady=10)

        self.stop_btn = tk.Button(frame, text="Stop Logging", state='disabled', command=self.stop_logging)
        self.stop_btn.grid(row=3, column=1, pady=10)

    def parse_filter(self, text):
        ids = set()
        for part in text.split(','):
            if '-' in part:
                try:
                    start, end = [int(x.strip(), 16 if 'x' in x else 10) for x in part.split('-')]
                    ids.update(range(start, end + 1))
                except:
                    continue
            elif part.strip():
                try:
                    ids.add(int(part.strip(), 16 if 'x' in part else 10))
                except:
                    continue
        return ids

    def start_logging(self):
        self.filter_ids = self.parse_filter(self.filter_entry.get())
        self.running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        threading.Thread(target=self.log_can_messages, daemon=True).start()

    def stop_logging(self):
        self.running = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')

    def log_can_messages(self):
        try:
            # Init CAN bus
            bus = can.interface.Bus(bustype='vector', channel=0, bitrate=500000, app_name='canoe')

            # Select file
            log_format = self.log_format.get()
            filename = filedialog.asksaveasfilename(defaultextension=f".{log_format}",
                                                    filetypes=[(log_format.upper(), f"*.{log_format}")])
            if not filename:
                self.stop_logging()
                return

            print(f"Logging to {filename}...")

            with open(filename, 'w', newline='') as f:
                writer = None
                if log_format == "csv":
                    writer = csv.writer(f)
                    writer.writerow(["Timestamp", "ID", "DLC", "Data", "Direction"])
                elif log_format == "json":
                    logs = []

                while self.running:
                    msg = bus.recv(1)
                    if msg:
                        if self.direction.get() == "rx" and msg.is_tx:
                            continue
                        if self.direction.get() == "tx" and not msg.is_tx:
                            continue
                        if self.filter_ids and msg.arbitration_id not in self.filter_ids:
                            continue

                        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(msg.timestamp))
                        data_hex = ' '.join(f'{b:02X}' for b in msg.data)
                        direction = "TX" if msg.is_tx else "RX"

                        if log_format in ["txt", "asc"]:
                            f.write(f"[{ts}] ID: 0x{msg.arbitration_id:X} DLC: {msg.dlc} Data: {data_hex} Dir: {direction}\n")
                        elif log_format == "csv":
                            writer.writerow([ts, f"0x{msg.arbitration_id:X}", msg.dlc, data_hex, direction])
                        elif log_format == "json":
                            logs.append({
                                "timestamp": ts,
                                "id": f"0x{msg.arbitration_id:X}",
                                "dlc": msg.dlc,
                                "data": data_hex,
                                "direction": direction
                            })
                        f.flush()

                if log_format == "json":
                    json.dump(logs, f, indent=4)

        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            try:
                bus.shutdown()
            except:
                pass

if __name__ == "__main__":
    root = tk.Tk()
    app = CANLoggerApp(root)
    root.mainloop()
