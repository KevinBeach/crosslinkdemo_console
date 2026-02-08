import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import time

# ---------------- Constants ----------------
UART_PORT = "COM3"  # Change this if your RISC-V UART appears on a different COM port
BAUDRATE = 115200
TIMEOUT = 1.0

# Sensor register addresses
REG_ANALOG_GAIN = "0157"
REG_EXPO_MSB    = "015A"
REG_EXPO_LSB    = "015B"


def get_available_ports():
    """Return list of (port, description) tuples."""
    ports = []
    for port in serial.tools.list_ports.comports():
        ports.append((port.device, f"{port.device} - {port.description}"))
    return ports


# ---------------- CCM (Color Correction Matrix) ----------------
CCM_COEFFS = [
    ("MRR", "05"), ("MRG", "06"), ("MRB", "07"),
    ("MGR", "08"), ("MGG", "09"), ("MGB", "0A"),
    ("MBR", "0B"), ("MBG", "0C"), ("MBB", "0D"),
]

# ---------------- Translation Matrix ----------------
TRANSLATION_COEFFS = [
    ("Translation R", "02"),
    ("Translation G", "03"),
    ("Translation B", "04"),
]


# ---------------- Serial helpers ----------------

class SensorLink:
    """Handles communication with the sensor firmware."""
    def __init__(self, port=None):
        self.ser = None
        self.port = port

    def connect(self, port):
        """Establish serial connection to the specified port."""
        if self.ser is not None:
            self.disconnect()

        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=BAUDRATE,
                timeout=TIMEOUT
            )
            self.port = port
            # Give device a moment to settle
            time.sleep(0.1)
            # Switch off verbose mode immediately
            self.send_cmd("V OFF")
            return True
        except Exception as e:
            raise RuntimeError(f"Failed to open UART port {port}: {e}")

    def disconnect(self):
        """Close the serial connection."""
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def is_connected(self):
        """Check if serial connection is active."""
        return self.ser is not None and self.ser.is_open

    # CCM helpers
    def ccm_read(self, addr):
        return self.send_cmd(f"C R {addr}")

    def ccm_write(self, addr, value):
        return self.send_cmd(f"C W {addr} {value}")

    # Translation Matrix helpers
    def translation_read(self, addr):
        return self.send_cmd(f"T R {addr}")

    def translation_write(self, addr, value):
        return self.send_cmd(f"T W {addr} {value}")

    # Upload both CCM and Translation matrices
    def ccm_upload(self):
        return self.send_cmd("C U")

    def send_cmd(self, cmd):
        """Send a command and return the first line of response."""
        if not self.is_connected():
            raise RuntimeError("Not connected to device.")

        # Send the command and read lines until we get a non-empty response
        self.ser.write((cmd + "\r\n").encode("ascii"))
        try:
            self.ser.flush()
        except Exception:
            pass

        deadline = time.time() + TIMEOUT
        while time.time() < deadline:
            line = self.ser.readline()
            if not line:
                continue
            try:
                text = line.decode("ascii", errors="ignore").strip()
            except Exception:
                text = ""

            # Remove common prompt characters (e.g. leading '>') and whitespace
            text = text.lstrip('> ').strip()
            if text:
                return text

        # No meaningful response received within timeout
        return ""

    def read_reg(self, addr):
        """Read a register from the sensor firmware."""
        return self.send_cmd(f"S R {addr}")

    def write_reg(self, addr, value):
        """Write a value to a register on the sensor firmware."""
        return self.send_cmd(f"S W {addr} {value}")


# ---------------- GUI ----------------

class SensorGUI(tk.Tk):
    """Tkinter GUI for controlling three sensor registers."""
    def __init__(self):
        super().__init__()
        self.title("Sensor Control - Not Connected")
        self.resizable(False, False)

        self.link = SensorLink()  # Not yet connected
        self.control_frame = None  # Will be created after connection
        self.port_var = tk.StringVar()

        self._build_connection_ui()

    def _build_connection_ui(self):
        """Build the connection selection frame."""
        conn_frame = ttk.Frame(self, padding=10)
        conn_frame.grid()

        ttk.Label(conn_frame, text="Select COM Port:", font=(None, 10, 'bold')).grid(
            row=0, column=0, sticky='w', padx=(0, 10)
        )

        # Port dropdown
        ports = get_available_ports()
        port_list = [desc for _, desc in ports]
        self.port_combo = ttk.Combobox(
            conn_frame, values=port_list, width=40, state='readonly'
        )
        self.port_combo.grid(row=0, column=1, padx=5)
        if port_list:
            self.port_combo.current(0)

        # Connect button
        self.connect_btn = ttk.Button(
            conn_frame, text="Connect", command=self._on_connect
        )
        self.connect_btn.grid(row=0, column=2, padx=5)

        # Refresh ports button
        ttk.Button(conn_frame, text="Refresh", command=self._refresh_ports).grid(
            row=0, column=3, padx=5
        )

        # Status label
        self.status_label = ttk.Label(
            conn_frame, text="Disconnected", foreground="red"
        )
        self.status_label.grid(row=1, column=0, columnspan=4, pady=(5, 0))

    def _refresh_ports(self):
        """Refresh the list of available ports."""
        ports = get_available_ports()
        port_list = [desc for _, desc in ports]
        self.port_combo['values'] = port_list
        if port_list and not self.port_combo.get():
            self.port_combo.current(0)

    def _on_connect(self):
        """Handle connect button press."""
        selected = self.port_combo.get()
        if not selected:
            messagebox.showwarning("No port", "Please select a COM port.")
            return

        # Extract port device from description (first part before ' - ')
        port_device = selected.split(' - ')[0]

        try:
            self.link.connect(port_device)
            self.title(f"Sensor Control - Connected to {port_device}")
            self.status_label.config(
                text=f"Connected to {port_device}",
                foreground="green"
            )
            self.connect_btn.config(state='disabled')
            self.port_combo.config(state='disabled')

            # Build the main control UI
            if self.control_frame is None:
                self._build_ui()

        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            self.status_label.config(text="Connection failed", foreground="red")

    def _build_ui(self):
        """Build the main control UI (sensor regs, CCM, translation)."""
        self.control_frame = ttk.Frame(self, padding=10)
        self.control_frame.grid(row=1, column=0, columnspan=1, sticky='ew')

        main = self.control_frame

        # Port label at the top
        ttk.Label(main, text=f"Connected to {UART_PORT}", foreground="green").grid(
            row=0, column=0, columnspan=4, pady=(0, 10)
        )

        # Rows: label, entry, read, write (sensor registers)
        self._make_row(main, 1, "Analog Gain", REG_ANALOG_GAIN, cmd_type='S', mode='hex')
        self._make_row(main, 2, "Exposure MSB", REG_EXPO_MSB, cmd_type='S', mode='hex')
        self._make_row(main, 3, "Exposure LSB", REG_EXPO_LSB, cmd_type='S', mode='hex')

        # CCM section header
        ttk.Label(main, text="Color Correction Matrix", font=(None, 10, 'bold')).grid(
            row=4, column=0, columnspan=4, pady=(8, 4), sticky='w'
        )

        # CCM coefficient rows start at row 5
        r = 5
        for name, addr in CCM_COEFFS:
            self._make_row(main, r, name, addr, cmd_type='C', mode='signed')
            r += 1

        # Translation Matrix section header
        ttk.Label(main, text="Translation Matrix", font=(None, 10, 'bold')).grid(
            row=r, column=0, columnspan=4, pady=(8, 4), sticky='w'
        )
        r += 1

        # Translation coefficient rows
        for name, addr in TRANSLATION_COEFFS:
            self._make_row(main, r, name, addr, cmd_type='T', mode='signed')
            r += 1

        # Verbose off and Upload buttons
        ttk.Button(main, text="Verbose Off", command=self._verbose_off).grid(
            row=r, column=0, columnspan=2, pady=(10, 5), sticky="ew"
        )
        ttk.Button(main, text="Upload to CCM", command=self._upload_ccm).grid(
            row=r, column=2, columnspan=2, pady=(10, 5), sticky="ew"
        )

        # Log box
        self.log = tk.Text(main, width=50, height=8, state="disabled")
        self.log.grid(row=r+1, column=0, columnspan=4, pady=(0, 0))

        # Disconnect button at bottom
        ttk.Button(main, text="Disconnect", command=self._on_disconnect).grid(
            row=r+2, column=0, columnspan=4, pady=(5, 0), sticky="ew"
        )

    def _make_row(self, parent, row, label, addr, cmd_type='S', mode='hex'):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")

        entry = ttk.Entry(parent, width=10)
        entry.grid(row=row, column=1, padx=5)

        # default cmd_type 'S' (sensor), mode 'hex'. For CCM pass cmd_type='C' and mode='signed'
        def make_read():
            return lambda: self._read(addr, entry, cmd_type=cmd_type, mode=mode)

        def make_write():
            return lambda: self._write(addr, entry, cmd_type=cmd_type, mode=mode)

        ttk.Button(parent, text="Read", command=make_read()).grid(row=row, column=2, padx=5)
        ttk.Button(parent, text="Write", command=make_write()).grid(row=row, column=3, padx=5)

    def _read(self, addr, entry, cmd_type='S', mode='hex'):
        """Read the register value and update the entry box.

        cmd_type: 'S' for sensor (S R), 'C' for CCM (C R), 'T' for translation (T R)
        mode: 'hex' to strip 0x prefix, 'signed' to display signed decimal
        """
        try:
            if cmd_type == 'C':
                resp = self.link.ccm_read(addr)
            elif cmd_type == 'T':
                resp = self.link.translation_read(addr)
            else:
                resp = self.link.read_reg(addr)

            self._log(f"READ {addr} -> {resp}")

            if not resp:
                display_val = ""
            else:
                # If response starts with 0x, strip that prefix; otherwise leave as-is
                if resp.lower().startswith('0x') and mode == 'hex':
                    display_val = resp[2:]
                else:
                    display_val = resp

            entry.delete(0, tk.END)
            entry.insert(0, display_val)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _write(self, addr, entry, cmd_type='S', mode='hex'):
        """Write the value from the entry box to the register.

        cmd_type: 'S' for sensor (S W), 'C' for CCM (C W), 'T' for translation (T W)
        mode: 'hex' to send hex digits (strip leading 0x), 'signed' to send signed decimal
        """
        value = entry.get().strip()
        if not value:
            return

        # Prepare value according to mode
        if mode == 'hex':
            # Strip optional 0x prefix
            if value.lower().startswith('0x'):
                value_to_send = value[2:]
            else:
                value_to_send = value

            if not value_to_send:
                messagebox.showwarning("Invalid input", "Please enter a valid hex value.")
                return

        elif mode == 'signed':
            # Accept leading + or - and integer digits
            try:
                intval = int(value, 10)
            except Exception:
                messagebox.showwarning("Invalid input", "Please enter a signed integer.")
                return

            # Validate range based on command type
            if cmd_type == 'T':
                min_val, max_val = -255, 255
                range_str = "(-255..255)"
            else:  # 'C' or other
                min_val, max_val = -99, 99
                range_str = "(-99..99)"

            if intval < min_val or intval > max_val:
                messagebox.showwarning("Out of range", f"Value must be between {min_val} and {max_val} {range_str}.")
                return

            # Send exactly as decimal string
            value_to_send = str(intval)

        else:
            value_to_send = value

        try:
            if cmd_type == 'C':
                resp = self.link.ccm_write(addr, value_to_send)
            elif cmd_type == 'T':
                resp = self.link.translation_write(addr, value_to_send)
            else:
                resp = self.link.write_reg(addr, value_to_send)
            self._log(f"WRITE {addr} = {value_to_send} -> {resp}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _upload_ccm(self):
        """Send the CCM upload command (C U)."""
        try:
            resp = self.link.ccm_upload()
            self._log(f"UPLOAD CCM -> {resp}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _verbose_off(self):
        """Send the Verbose Off command to the sensor."""
        try:
            resp = self.link.send_cmd("V OFF")
            self._log(f"VERBOSE OFF -> {resp}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_disconnect(self):
        """Handle disconnect button press."""
        self.link.disconnect()
        self.title("Sensor Control - Not Connected")
        self.status_label.config(text="Disconnected", foreground="red")
        self.connect_btn.config(state='normal')
        self.port_combo.config(state='readonly')

        if self.control_frame is not None:
            self.control_frame.destroy()
            self.control_frame = None

    def _log(self, text):
        """Append a line to the log box."""
        self.log.configure(state="normal")
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")


# ---------------- Main ----------------

# Main entry point
if __name__ == "__main__":
    app = SensorGUI()
    app.mainloop()
