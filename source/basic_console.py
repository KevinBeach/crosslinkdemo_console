import tkinter as tk
from tkinter import ttk, messagebox
import serial

# ---------------- Constants ----------------
UART_PORT = "COM3"  # Change this if your RISC-V UART appears on a different COM port
BAUDRATE = 115200
TIMEOUT = 0.5

# Sensor register addresses
REG_ANALOG_GAIN = "0157"
REG_EXPO_MSB    = "015A"
REG_EXPO_LSB    = "015B"


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
        except Exception as e:
            raise RuntimeError(f"Failed to open UART port {UART_PORT}: {e}")

    def send_cmd(self, cmd):
        """Send a command and return the first line of response."""
        self.ser.write((cmd + "\r\n").encode("ascii"))
        return self.ser.readline().decode("ascii", errors="ignore").strip()

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

        # Rows: label, entry, read, write
        self._make_row(main, 1, "Analog Gain", REG_ANALOG_GAIN)
        self._make_row(main, 2, "Exposure MSB", REG_EXPO_MSB)
        self._make_row(main, 3, "Exposure LSB", REG_EXPO_LSB)

        # Log box
        self.log = tk.Text(main, width=50, height=6, state="disabled")
        self.log.grid(row=4, column=0, columnspan=4, pady=(10, 0))

    def _make_row(self, parent, row, label, addr):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")

        entry = ttk.Entry(parent, width=10)
        entry.grid(row=row, column=1, padx=5)

        ttk.Button(parent, text="Read", command=lambda: self._read(addr, entry)).grid(row=row, column=2, padx=5)
        ttk.Button(parent, text="Write", command=lambda: self._write(addr, entry)).grid(row=row, column=3, padx=5)

    def _read(self, addr, entry):
        """Read the register value and update the entry box."""
        try:
            resp = self.link.read_reg(addr)
            self._log(f"READ {addr} -> {resp}")
            entry.delete(0, tk.END)
            entry.insert(0, resp)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _write(self, addr, entry):
        """Write the value from the entry box to the register."""
        value = entry.get().strip()
        if not value:
            return
        try:
            resp = self.link.write_reg(addr, value)
            self._log(f"WRITE {addr} = {value} -> {resp}")
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
