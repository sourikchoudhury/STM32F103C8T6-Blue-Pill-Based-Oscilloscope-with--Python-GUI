# STM32F103C8T6 (Blue Pill)-Based-Oscilloscope-with -Python-GUI

## Overview 
A Low-Cost DIY oscilloscope project that captures analog signals using the STM32F103C8T6 microcontroller and streams sampled data to a Windows PC over USB CDC for real-time waveform visualization using a custom Python GUI.

The project combines embedded firmware, ADC-based data acquisition, DMA, USB communication, and desktop visualization into a compact electronics test instrument.

<p align="center">
  <img src="images\IMG_20261013_183253.jpg" alt="Prototype Full" width="800">
</p>

---

## Working 
The STM32 samples an analog input from **Custom made Signal Generator (555-Timer based)** using its ADC peripheral. DMA transfers conversion results into a memory buffer, and the firmware streams acquired data over USB CDC. A Python application receives the data and displays the waveform with interactive controls and signal measurements.

---

## Features

- ADC-based analog signal acquisition

- DMA-assisted sample buffering

- USB CDC communication with a Windows PC

- Python-based graphical interface

- Real-time waveform visualization

- Serial-port connection controls

- Waveform zoom and pan controls

- Pause and resume functionality

- Frequency and period measurements

- Instantaneous voltage, minimum, maximum, and peak-to-peak measurements

- ADC and voltage scales for waveform inspection

- Screenshot capture

---

## Gallery

<p align="center">
  <img src="images\IMG_20261013_014545.jpeg" alt="Hardware" width="600">
</p>

<p align="center">
  <img src="images\Screenshot_1433.jpg" alt="Waveform-GUI" width="600">
</p>

---

## Hardware Components

- **STM32F103C8T6 Blue Pill** - Main microcontroller and ADC acquisition

- **ST-Link V2** - Firmware programming and debugging

- **NE555 timer IC** - Test signal generation

- **Resistors and capacitor** - Set the NE555 oscillator timing

- **USB data cable** - Power/USB connection to the PC, as supported by the board setup

- **Breadboard and jumper wires** - Circuit assembly and signal connections

- **PC running Windows** - Firmware communication and waveform visualization

--- 

## Software and Tools

### Embedded Firmware

- STM32CubeMX

- STM32CubeIDE

- STM32 HAL

- Embedded C

- ADC continuous conversion

- DMA-based data buffering

- USB CDC

### PC Applications

- Python 3

- Tkinter

- Matplotlib

- NumPy

- PySerial

---

## How It Works

### Generate the Test Signal
An NE555 timer is configured in astable mode to generate a periodic test waveform. This provides a convenient hardware-generated input for testing the oscilloscope acquisition path.

### Acquire the Signal
The generated waveform is connected to the STM32 ADC input. The ADC converts the analog input voltage into digital sample values.

### Buffer Samples Using DMA
DMA moves ADC conversion results into memory buffers, reducing the need for the CPU to handle each conversion individually.

### Transmit Samples over USB
The firmware sends the acquired sample data to the PC using USB CDC. The PC application reads the incoming stream through a serial interface.

### Visualize the Waveform
The Python GUI processes the received data and plots the waveform using Matplotlib. Tkinter provides the application interface and interactive controls for inspecting the signal.

---

## Software Setup

### Install Python
Install Python 3 if it is not already available on your system.

### Install Dependencies
**python -m pip install pyserial matplotlib numpy**

Tkinter is included with many standard Python installations. On some Linux distributions, it may need to be installed separately.

### Connect the Hardware
- Connect the NE555 signal generator output to the STM32 ADC input used by the firmware.

- Connect the signal generator ground to the STM32 ground.

- Connect the Blue Pill to the PC using a suitable USB data connection.

- Confirm that the STM32 firmware is programmed and running.

- Identify the COM port assigned to the USB CDC device.

Important: Ensure the ADC input voltage remains within the STM32's permitted input range. Do not connect a signal generator output directly if its voltage can exceed that range.

### Run the Python GUI
**python stm32_usb_oscilloscope.py**

[Python File](python_gui\stm32_usb_oscilloscope.py)

Replace the filename with the actual name of your Python script if it differs.

If the COM port is configured in the source code, update it to match the port assigned by your computer. The Python application's serial settings must also match the firmware's communication format.

---

## Current Limitations

This is an experimental DIY oscilloscope intended for embedded systems learning and basic signal visualization. Its measurement capabilities and performance depend on the ADC configuration, sampling behavior, firmware data transfer, USB throughput, and GUI processing.

- The displayed sampling rate should be validated against the actual acquisition and data-transfer implementation.

- Frequency and voltage measurements should be checked against known reference signals and suitable test equipment.

- The project should not be treated as a calibrated laboratory oscilloscope.

- Input protection, analog conditioning, and bandwidth limitations should be considered before connecting signals other than the intended low-voltage test source.

---

## Future Improvements

Potential improvements include:

- More reliable continuous acquisition and buffering.

- Improved trigger and waveform stability.

- Calibration and validation of voltage and frequency measurements.

- Adjustable time and voltage scales.

- Better handling of serial data loss and buffer overruns.

- Analog input conditioning and protection.

- Support for additional test signals and input ranges.

---

## Skills Demonstrated

- Embedded C programming

- STM32 microcontroller peripherals

- ADC configuration and analog signal acquisition

- DMA and memory buffering

- USB CDC communication

- NE555 timer circuit design

- Python desktop GUI development

- Data visualization with Matplotlib

- Hardware–software integration and debugging

---

## Demo

Full Demo Video will be uploaded soon.

---

## Licence

---