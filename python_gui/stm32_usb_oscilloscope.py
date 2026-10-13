import tkinter as tk

from tkinter import ttk, filedialog, messagebox

import serial

import serial.tools.list_ports

import threading

import queue

import time



import numpy as np

import matplotlib

matplotlib.use("TkAgg")

from matplotlib.figure import Figure

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg



# ============================================================

# STM32 BLUE PILL USB CDC OSCILLOSCOPE - DARK EDITION

#

# STM32 packet:

#   uint16_t usb_packet[32];

#   CDC_Transmit_FS((uint8_t *)usb_packet, sizeof(usb_packet));

#

# Therefore:

#   32 samples = 64 bytes

#

# ADC:

#   12-bit: 0...4095

#   Vref:   3.3 V

#

# IMPORTANT:

# Frequency calculation requires a known ADC sample rate.

# Set SAMPLE_RATE_HZ below to the ACTUAL measured/configured

# ADC sampling rate. Do not assume USB packet rate is the

# sampling rate.

# ============================================================



SERIAL_PORT = "COM5"

BAUD_RATE = 115200



PACKET_SAMPLES = 32

PACKET_BYTES = 64



ADC_MAX = 4095

VREF = 3.3



# ------------------------------------------------------------

# IMPORTANT FREQUENCY SETTING

# ------------------------------------------------------------

# Your current ADC configuration theoretically gives roughly

# 857 kS/s with:

#   ADC clock = 12 MHz

#   sample time = 1.5 cycles

#

# Use this as an initial value ONLY.

# We can calibrate this later using your known 12 kHz source.

SAMPLE_RATE_HZ = 142857.143



DISPLAY_SAMPLES = 4096



# Dark oscilloscope theme

BLACK = "#000000"

WHITE = "#ffffff"

GREEN = "#00ff3c"

GRID = "#404040"

DARK_PANEL = "#111111"

BUTTON_BG = "#222222"

BUTTON_ACTIVE = "#333333"

RED = "#ff4545"

YELLOW = "#fff200"





class OscilloscopeApp:

    def __init__(self, root):

        self.root = root

        self.root.title("STM32 Blue Pill USB Oscilloscope")

        self.root.geometry("1250x800")

        self.root.minsize(950, 650)

        self.root.configure(bg=BLACK)



        self.running = True

        self.connected = False

        self.paused = False

        self.serial_port = None



        self.data_queue = queue.Queue()

        self.data_lock = threading.Lock()



        self.samples = np.zeros(DISPLAY_SAMPLES, dtype=np.uint16)

        self.sample_count = 0

        self.total_packets = 0

        self.bad_packets = 0



        # Frequency is calculated from the latest acquired data.

        self.frequency_hz = 0.0

        self.frequency_valid = False

        self.frequency_history = []



        self.x_zoom = 1.0

        self.x_center = DISPLAY_SAMPLES / 2



        self.port_var = tk.StringVar(value=SERIAL_PORT)

        self.status_var = tk.StringVar(value="Disconnected")

        self.frequency_var = tk.StringVar(value="Frequency: -- Hz")

        self.period_var = tk.StringVar(value="Period: --")

        self.value_var = tk.StringVar(value="ADC: --")

        self.voltage_var = tk.StringVar(value="Voltage: --")

        self.min_var = tk.StringVar(value="Min: --")

        self.max_var = tk.StringVar(value="Max: --")

        self.vpp_var = tk.StringVar(value="Vpp: --")

        self.packet_var = tk.StringVar(value="Packets: 0")

        self.sample_var = tk.StringVar(value="Samples: 0")

        self.pause_var = tk.StringVar(value="PAUSED")



        self._build_gui()

        self._setup_plot()



        self.root.protocol("WM_DELETE_WINDOW", self.close)



        self.root.after(20, self.process_serial_data)

        self.root.after(40, self.update_plot)

        self.root.after(250, self.update_frequency)



        self.root.after(300, self.connect_serial)


    # ========================================================

    # GUI

    # ========================================================

    def _build_gui(self):

        # ----------------------------------------------------

        # Frequency display at very top

        # ----------------------------------------------------

        frequency_frame = tk.Frame(

            self.root,

            bg=BLACK,

            highlightbackground="#303030",

            highlightthickness=1

        )

        frequency_frame.pack(fill="x", padx=12, pady=(10, 5))



        tk.Label(

            frequency_frame,

            textvariable=self.frequency_var,

            bg=BLACK,

            fg=GREEN,

            font=("Consolas", 24, "bold")

        ).pack(side="left", padx=18, pady=8)



        tk.Label(

            frequency_frame,

            textvariable=self.period_var,

            bg=BLACK,

            fg=WHITE,

            font=("Consolas", 11)

        ).pack(side="left", padx=15)



        tk.Label(

            frequency_frame,

            textvariable=self.pause_var,

            bg=BLACK,

            fg=RED,

            font=("Consolas", 11, "bold")

        ).pack(side="right", padx=18)



        # ----------------------------------------------------

        # Controls

        # ----------------------------------------------------

        controls = tk.Frame(self.root, bg=BLACK)

        controls.pack(fill="x", padx=12, pady=(2, 5))



        self._label(controls, "PORT").pack(side="left", padx=(4, 5))



        self.port_combo = ttk.Combobox(

            controls,

            textvariable=self.port_var,

            width=9,

            state="normal"

        )

        self.port_combo.pack(side="left", padx=3)



        self._button(

            controls, "Refresh", self.refresh_ports

        ).pack(side="left", padx=3)



        self.connect_button = self._button(

            controls, "Connect", self.toggle_connection

        )

        self.connect_button.pack(side="left", padx=3)



        self.pause_button = self._button(

            controls, "Pause", self.toggle_pause

        )

        self.pause_button.pack(side="left", padx=(15, 3))



        self._button(

            controls, "Clear", self.clear_display

        ).pack(side="left", padx=3)



        self._button(

            controls, "Screenshot", self.save_screenshot

        ).pack(side="right", padx=3)



        # ----------------------------------------------------

        # Plot

        # ----------------------------------------------------

        plot_frame = tk.Frame(self.root, bg=BLACK)

        plot_frame.pack(fill="both", expand=True, padx=12, pady=4)



        self.figure = Figure(

            figsize=(10, 6),

            dpi=100,

            facecolor=BLACK

        )



        self.ax = self.figure.add_subplot(111)



        self.figure.subplots_adjust(

            # Keep the original plot width/position. The extra voltage scale
            # must fit in the existing left margin, not push the waveform right.
            left=0.075,

            right=0.985,

            top=0.95,

            bottom=0.105

        )



        self.canvas = FigureCanvasTkAgg(

            self.figure,

            master=plot_frame

        )

        self.canvas.get_tk_widget().pack(

            fill="both",

            expand=True

        )



        self.canvas.mpl_connect(

            "scroll_event",

            self.on_scroll

        )

        self.canvas.mpl_connect(

            "button_press_event",

            self.on_mouse_press

        )

        self.canvas.mpl_connect(

            "motion_notify_event",

            self.on_mouse_motion

        )

        self.canvas.mpl_connect(

            "button_release_event",

            self.on_mouse_release

        )



        # ----------------------------------------------------

        # Bottom information bar

        # ----------------------------------------------------

        bottom = tk.Frame(self.root, bg=BLACK)

        bottom.pack(fill="x", padx=12, pady=(4, 10))



        self._label(bottom, "ZOOM").pack(

            side="left", padx=(4, 5)

        )



        self._button(

            bottom, "−", self.zoom_out, width=6

        ).pack(side="left", padx=2)



        self._button(

            bottom, "Reset", self.reset_zoom, width=7

        ).pack(side="left", padx=2)



        self._button(

            bottom, "+", self.zoom_in, width=6

        ).pack(side="left", padx=2)



        # ----------------------------------------------------
        # Graph drag controls
        # ----------------------------------------------------



        self._button(
            bottom, "◀", self.drag_right, width=4
        ).pack(side="left", padx=(12, 2))

        self._label(bottom, "DRAG").pack(
            side="left", padx=2
        )

        self._button(
            bottom, "▶", self.drag_left, width=4
        ).pack(side="left", padx=2)





        info = tk.Frame(

            bottom,

            bg=DARK_PANEL,

            highlightbackground="#303030",

            highlightthickness=1

        )

        info.pack(side="right")



        for var in (

            self.value_var,

            self.voltage_var,

            self.min_var,

            self.max_var,

            self.vpp_var,

            self.packet_var,

            self.sample_var

        ):

            tk.Label(

                info,

                textvariable=var,

                bg=DARK_PANEL,

                fg=WHITE,

                font=("Consolas", 9, "bold"),

                padx=8,

                pady=5

            ).pack(side="left")



        tk.Label(

            bottom,

            textvariable=self.status_var,

            bg=BLACK,

            fg=WHITE,

            font=("Consolas", 9)

        ).pack(side="left", padx=18)



    def _label(self, parent, text):

        return tk.Label(

            parent,

            text=text,

            bg=BLACK,

            fg=WHITE,

            font=("Consolas", 9, "bold")

        )



    def _button(self, parent, text, command, width=9):

        return tk.Button(

            parent,

            text=text,

            command=command,

            bg=BUTTON_BG,

            fg=WHITE,

            activebackground=BUTTON_ACTIVE,

            activeforeground=WHITE,

            relief="flat",

            bd=0,

            width=width,

            padx=7,

            pady=4,

            font=("Consolas", 9, "bold")

        )



    # ========================================================

    # Plot setup

    # ========================================================

    def _setup_plot(self):

        self.ax.set_facecolor(BLACK)



        x = np.arange(DISPLAY_SAMPLES)



        self.line, = self.ax.plot(

            x,

            self.samples,

            color=GREEN,

            linewidth=1.3,

            antialiased=True

        )



        self.ax.set_xlim(

            0,

            DISPLAY_SAMPLES - 1

        )

        self.ax.set_ylim(

            0,

            ADC_MAX

        )



        self.ax.set_xlabel(

            "Sample number",

            color=WHITE,

            fontsize=10,

            fontweight="bold"

        )

        self.ax.set_ylabel(

            "ADC value (0–4095) /",

            color=WHITE,

            fontsize=10,

            fontweight="bold"

        )
        self.ax.yaxis.set_label_coords(-0.07, 0.3)


        self.ax.set_title(

            "STM32 ADC Waveform",

            color=WHITE,

            fontsize=12,

            fontweight="bold",

            pad=8

        )



        self.ax.tick_params(

            axis="both",

            colors=WHITE,

            labelcolor=WHITE

        )



        for spine in self.ax.spines.values():

            spine.set_color(WHITE)



        self.ax.grid(

            True,

            color=GRID,

            linewidth=0.55,

            alpha=0.8

        )


        # Additional voltage scale on the LEFT, directly mapped to ADC counts.
        # The ADC axis and voltage axis share the same vertical coordinates,
        # so ADC=0 maps to 0.00 V and ADC=ADC_MAX maps to VREF.
        from matplotlib.ticker import FuncFormatter

        self.ax_voltage = self.ax.twinx()
        self.ax_voltage.set_ylim(0, ADC_MAX)
        self.ax_voltage.set_yticks(self.ax.get_yticks())
        self.ax_voltage.yaxis.set_major_formatter(
            FuncFormatter(lambda adc, _pos: f"{adc * VREF / ADC_MAX:.2f}")
        )
        self.ax_voltage.spines["right"].set_visible(False)
        self.ax_voltage.spines["left"].set_position(("outward", 34))
        self.ax_voltage.spines["left"].set_color("yellow")
        self.ax_voltage.yaxis.set_label_position("left")
        self.ax_voltage.yaxis.tick_left()
        self.ax_voltage.set_ylabel(
            "/ Voltage (V)",
            color="yellow",
            fontsize=10,
            fontweight="bold",
            labelpad=3,
        )
        self.ax_voltage.tick_params(
            axis="y", colors="yellow", labelcolor="yellow",
            direction="out", pad=3,
        )
        self.ax_voltage.yaxis.set_label_coords(-0.07, 0.55)
        self.ax_voltage.xaxis.set_visible(False)
        self.ax_voltage.patch.set_visible(False)
        self.ax_voltage.set_navigate(False)



        self.canvas.draw_idle()



    # ========================================================

    # Serial

    # ========================================================

    def refresh_ports(self):

        ports = [

            p.device

            for p in serial.tools.list_ports.comports()

        ]



        if SERIAL_PORT in ports:

            ordered = [SERIAL_PORT] + [

                p for p in ports if p != SERIAL_PORT

            ]

        else:

            ordered = ports



        self.port_combo["values"] = ordered



        if ordered and self.port_var.get() not in ordered:

            self.port_var.set(ordered[0])



    def connect_serial(self):

        if self.connected:

            return



        port = self.port_var.get().strip()



        if not port:

            self.status_var.set("No COM port selected")

            return



        try:

            self.serial_port = serial.Serial(

                port=port,

                baudrate=BAUD_RATE,

                timeout=0.05

            )



            self.connected = True



            self.connect_button.config(

                text="Disconnect"

            )



            self.status_var.set(

                f"Connected: {port}"

            )



            self.serial_thread = threading.Thread(

                target=self.serial_reader,

                daemon=True

            )

            self.serial_thread.start()



        except Exception as exc:

            self.connected = False

            self.status_var.set(

                f"Connection failed: {exc}"

            )



    def toggle_connection(self):

        if self.connected:

            self.disconnect_serial()

        else:

            self.connect_serial()



    def disconnect_serial(self):

        self.connected = False



        try:

            if self.serial_port:

                self.serial_port.close()

        except Exception:

            pass



        self.serial_port = None



        self.connect_button.config(

            text="Connect"

        )



        self.status_var.set("Disconnected")



    def serial_reader(self):

        """

        Reads exactly the 64-byte STM32 application packet.



        uint16_t values are little-endian on STM32F103.

        """

        receive_buffer = bytearray()



        while self.running and self.connected:

            try:

                chunk = self.serial_port.read(

                    self.serial_port.in_waiting or 1

                )



                if not chunk:

                    continue



                receive_buffer.extend(chunk)



                # Reassemble arbitrary serial read boundaries

                # into exact 64-byte application packets.

                while len(receive_buffer) >= PACKET_BYTES:

                    packet = bytes(

                        receive_buffer[:PACKET_BYTES]

                    )

                    del receive_buffer[:PACKET_BYTES]



                    values = np.frombuffer(

                        packet,

                        dtype="<u2"

                    ).copy()



                    values = np.clip(

                        values,

                        0,

                        ADC_MAX

                    ).astype(np.uint16)



                    self.data_queue.put(values)

                    self.total_packets += 1



            except (

                serial.SerialException,

                OSError

            ):

                if self.running:

                    self.root.after(

                        0,

                        lambda: self.status_var.set(

                            "USB connection lost"

                        )

                    )

                break



            except Exception:

                self.bad_packets += 1



    # ========================================================

    # Data processing

    # ========================================================

    def process_serial_data(self):

        if not self.paused:

            try:

                while True:

                    values = self.data_queue.get_nowait()



                    with self.data_lock:

                        n = len(values)



                        if n >= DISPLAY_SAMPLES:

                            self.samples[:] = (

                                values[-DISPLAY_SAMPLES:]

                            )

                        else:

                            self.samples = np.roll(

                                self.samples,

                                -n

                            )

                            self.samples[-n:] = values



                        self.sample_count += n



            except queue.Empty:

                pass



        else:

            # While paused, discard newly arriving data.

            # The frozen waveform remains unchanged.

            try:

                while True:

                    self.data_queue.get_nowait()

            except queue.Empty:

                pass



        # Refresh status fields on the GUI thread; Tkinter is not updated
        # from the background serial-reader thread.
        with self.data_lock:
            display_data = self.samples.copy()
            acquired_samples = self.sample_count

        self.packet_var.set(f"Packets: {self.total_packets}")
        self.sample_var.set(f"Samples: {acquired_samples}")

        if acquired_samples > 0:
            adc_now = int(display_data[-1])
            adc_min = int(np.min(display_data))
            adc_max = int(np.max(display_data))
            voltage_now = adc_now * VREF / ADC_MAX
            vpp = (adc_max - adc_min) * VREF / ADC_MAX
            self.value_var.set(f"ADC: {adc_now}")
            self.voltage_var.set(f"Voltage: {voltage_now:.3f} V")
            self.min_var.set(f"Min: {adc_min}")
            self.max_var.set(f"Max: {adc_max}")
            self.vpp_var.set(f"Vpp: {vpp:.3f} V")
        else:
            self.value_var.set("ADC: --")
            self.voltage_var.set("Voltage: --")
            self.min_var.set("Min: --")
            self.max_var.set("Max: --")
            self.vpp_var.set("Vpp: --")

        if self.running:

            self.root.after(

                20,

                self.process_serial_data

            )



    # ========================================================

    # Frequency measurement

    # ========================================================

    def update_frequency(self):

        """Update a stabilized frequency estimate from the acquired waveform."""

        if not self.paused:

            with self.data_lock:

                data = self.samples.astype(np.float64).copy()



            freq = self.measure_frequency(data)



            if freq is not None:

                # Smooth several independent measurements.  This prevents

                # the displayed value from jumping when a sampled edge moves

                # by one ADC sample between updates.

                self.frequency_history.append(freq)

                if len(self.frequency_history) > 5:

                    self.frequency_history.pop(0)



                stable_freq = float(np.median(self.frequency_history))

                self.frequency_hz = stable_freq

                self.frequency_valid = True



                if stable_freq >= 1000:

                    self.frequency_var.set(

                        f"Frequency: {stable_freq / 1000:.3f} kHz"

                    )

                else:

                    self.frequency_var.set(

                        f"Frequency: {stable_freq:.2f} Hz"

                    )



                period = 1.0 / stable_freq



                if period >= 0.001:

                    self.period_var.set(

                        f"Period: {period * 1000:.3f} ms"

                    )

                else:

                    self.period_var.set(

                        f"Period: {period * 1e6:.2f} µs"

                    )

            else:

                self.frequency_history.clear()

                self.frequency_valid = False

                self.frequency_var.set(

                    "Frequency: -- Hz"

                )

                self.period_var.set(

                    "Period: --"

                )



        if self.running:

            self.root.after(250, self.update_frequency)



    def measure_frequency(self, data):

        """

        Measure frequency from many rising edges across the full display.



        The edge positions are sub-sample interpolated, then a straight-line

        fit across ALL detected cycles estimates one average samples/cycle.

        This is more stable than measuring each adjacent cycle independently.



        IMPORTANT:

        SAMPLE_RATE_HZ must be the actual ADC sampling rate for an accurate

        absolute frequency. USB packet size does not determine sample rate.

        """

        if len(data) < 512:

            return None



        low = float(np.percentile(data, 5))

        high = float(np.percentile(data, 95))

        amplitude = high - low



        if amplitude < 30:

            return None



        # Use the midpoint of the measured low/high levels as the edge

        # threshold.  A separate hysteresis band prevents noise from

        # creating multiple crossings around an edge.

        threshold = (low + high) * 0.5

        hysteresis = max(8.0, amplitude * 0.08)

        lower = threshold - hysteresis

        upper = threshold + hysteresis



        crossings = []

        armed = True



        for i in range(1, len(data)):

            if armed:

                if data[i - 1] <= lower and data[i] >= upper:

                    y1 = data[i - 1]

                    y2 = data[i]



                    if y2 != y1:

                        frac = (threshold - y1) / (y2 - y1)

                        frac = float(np.clip(frac, 0.0, 1.0))

                    else:

                        frac = 0.0



                    crossings.append((i - 1) + frac)

                    armed = False

            elif data[i] <= lower:

                armed = True



        if len(crossings) < 4:

            return None



        crossings = np.asarray(crossings, dtype=np.float64)



        # Fit crossing position = intercept + cycle_number * period.

        # The slope uses all cycles, so one slightly misplaced edge has much

        # less influence on the result than a single-cycle period measurement.

        cycle_numbers = np.arange(len(crossings), dtype=np.float64)

        period_samples = float(

            np.polyfit(cycle_numbers, crossings, 1)[0]

        )



        if not np.isfinite(period_samples) or period_samples <= 2.0:

            return None



        frequency = SAMPLE_RATE_HZ / period_samples



        if not np.isfinite(frequency) or frequency <= 0:

            return None



        # Reject implausible edge-detection results.

        if frequency > SAMPLE_RATE_HZ / 2.0:

            return None



        return frequency



    # ========================================================

    # Plot update

    # ========================================================

    def update_plot(self):

        with self.data_lock:

            data = self.samples.astype(

                np.float64

            ).copy()



        self.line.set_ydata(data)

        self.apply_x_view()



        if self.running:

            self.canvas.draw_idle()

            self.root.after(

                40,

                self.update_plot

            )



    # ========================================================

    # Pause

    # ========================================================

    def toggle_pause(self):

        self.paused = not self.paused



        if self.paused:

            self.pause_button.config(

                text="Resume"

            )

            self.pause_var.set(

                "PAUSED — waveform frozen"

            )



            self.status_var.set(

                "Paused: analyse the frozen waveform"

            )



        else:

            self.pause_button.config(

                text="Pause"

            )

            self.pause_var.set("")

            self.status_var.set(

                "Live acquisition"

            )



    # ========================================================

    # Zoom

    # ========================================================

    def apply_x_view(self):

        total = DISPLAY_SAMPLES



        visible = max(

            32,

            int(total / self.x_zoom)

        )



        left = (

            self.x_center -

            visible / 2

        )



        right = (

            self.x_center +

            visible / 2

        )



        if left < 0:

            right -= left

            left = 0



        if right > total - 1:

            left -= (

                right -

                (total - 1)

            )

            right = total - 1



        left = max(0, left)

        right = min(total - 1, right)



        self.ax.set_xlim(

            left,

            right

        )



    def zoom_in(self):

        self.x_zoom = min(

            self.x_zoom * 1.6,

            64.0

        )

        self.apply_x_view()

        self.canvas.draw_idle()



    def zoom_out(self):

        self.x_zoom = max(

            self.x_zoom / 1.6,

            1.0

        )

        self.apply_x_view()

        self.canvas.draw_idle()



    def reset_zoom(self):

        self.x_zoom = 1.0

        self.x_center = (

            DISPLAY_SAMPLES / 2

        )

        self.apply_x_view()

        self.canvas.draw_idle()
    # =======================================================

    # DRAG

    # ======================================================


    def drag_right(self):
        """Move the waveform to the right."""
        left, right = self.ax.get_xlim()
        shift = (right - left) * 0.05
        self.x_center -= shift
        self.apply_x_view()
        self.canvas.draw_idle()

    def drag_left(self):
        """Move the waveform to the left."""
        left, right = self.ax.get_xlim()
        shift = (right - left) * 0.05
        self.x_center += shift
        self.apply_x_view()
        self.canvas.draw_idle()



    def on_scroll(self, event):

        # Accept events from either overlaid Y-axis. The voltage axis
        # can be the axis Matplotlib reports under the mouse pointer.
        if event.inaxes not in (self.ax, self.ax_voltage):

            return



        if event.xdata is None:

            return



        old_zoom = self.x_zoom



        if event.button == "up":

            self.x_zoom = min(

                self.x_zoom * 1.35,

                64.0

            )



        elif event.button == "down":

            self.x_zoom = max(

                self.x_zoom / 1.35,

                1.0

            )

        else:

            return



        ratio = (

            old_zoom /

            self.x_zoom

        )



        self.x_center = (

            event.xdata +

            (

                self.x_center -

                event.xdata

            ) * ratio

        )



        self.apply_x_view()

        self.canvas.draw_idle()



    # ========================================================

    # Pan with left mouse button

    # ========================================================

    def on_mouse_press(self, event):

        if (

            event.inaxes in (self.ax, self.ax_voltage)

            and event.button == 1

            and event.xdata is not None

        ):

            self.drag_start_x = event.xdata

            self.drag_start_center = self.x_center



    def on_mouse_motion(self, event):

        if (

            event.inaxes in (self.ax, self.ax_voltage)

            and event.xdata is not None

            and hasattr(self, "drag_start_x")

            and self.drag_start_x is not None

        ):

            delta = (

                self.drag_start_x -

                event.xdata

            )



            self.x_center = (

                self.drag_start_center +

                delta

            )



            self.apply_x_view()

            self.canvas.draw_idle()



    def on_mouse_release(self, event):

        if event.button == 1:

            self.drag_start_x = None



    # ========================================================

    # Screenshot

    # ========================================================

    def save_screenshot(self):

        timestamp = time.strftime(

            "%Y%m%d_%H%M%S"

        )



        filename = filedialog.asksaveasfilename(

            title="Save oscilloscope screenshot",

            initialfile=(

                f"oscilloscope_{timestamp}.png"

            ),

            defaultextension=".png",

            filetypes=[

                ("PNG image", "*.png"),

                ("JPEG image", "*.jpg"),

                ("All files", "*.*")

            ]

        )



        if not filename:

            return



        try:

            self.figure.savefig(

                filename,

                dpi=180,

                facecolor=BLACK,

                bbox_inches="tight"

            )



            self.status_var.set(

                f"Screenshot saved: {filename}"

            )



        except Exception as exc:

            messagebox.showerror(

                "Screenshot error",

                str(exc)

            )



    # ========================================================

    # Clear

    # ========================================================

    def clear_display(self):

        with self.data_lock:

            self.samples[:] = 0

            self.sample_count = 0

            self.total_packets = 0

            self.value_var.set("ADC: --")
            self.voltage_var.set("Voltage: --")
            self.min_var.set("Min: --")
            self.max_var.set("Max: --")
            self.vpp_var.set("Vpp: --")
            self.packet_var.set("Packets: 0")
            self.sample_var.set("Samples: 0")

            self.frequency_valid = False

            self.frequency_history.clear()



        self.frequency_var.set(

            "Frequency: --"

        )

        self.period_var.set(

            "Period: --"

        )



        self.status_var.set(

            "Display cleared"

        )



    # ========================================================

    # Close

    # ========================================================

    def close(self):

        self.running = False

        self.connected = False



        try:

            if self.serial_port:

                self.serial_port.close()

        except Exception:

            pass



        self.root.destroy()





def main():

    root = tk.Tk()

    app = OscilloscopeApp(root)

    root.mainloop()





if __name__ == "__main__":

    main()
