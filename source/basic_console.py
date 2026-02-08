import tkinter as tk
from tkinter import ttk, messagebox
import serial
import time

# ---------------- Constants ----------------
UART_PORT = "COM3"  # Change this if your RISC-V UART appears on a different COM port
BAUDRATE = 115200
TIMEOUT = 1.0

# Sensor register addresses
REG_ANALOG_GAIN = "0157"
REG_EXPO_MSB    = "015A"
REG_EXPO_LSB    = "015B"


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
    def __init__(self):
        try:
            self.ser = serial.Serial(
                port=UART_PORT,
                baudrate=BAUDRATE,
                timeout=TIMEOUT
            )
             # Switch off verbose mode immediately
            self.send_cmd("V OFF")
        except Exception as e:
            raise RuntimeError(f"Failed to open UART port {UART_PORT}: {e}")

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
    def __init__(self, link):
        super().__init__()
        self.title("Sensor Control")
        self.resizable(False, False)

        self.link = link

        self._build_ui()

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.grid()

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

    def _log(self, text):
        """Append a line to the log box."""
        self.log.configure(state="normal")
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")


# ---------------- Main ----------------

if __name__ == "__main__":
    try:
        link = SensorLink()
    except Exception as e:
        messagebox.showerror("Startup error", str(e))
        raise

    app = SensorGUI(link)
    app.mainloop()
