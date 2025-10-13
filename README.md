# RF Signal Recording and Playback

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/RedPitaya/rec_and_play)
[![OS](https://img.shields.io/badge/OS-Red%20Pitaya%20Linux-green.svg)](https://redpitaya.com/)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

> Record RF signal pulses from IN1/IN2 and replay them on OUT1/OUT2 using Deep Memory Acquisition/Generation

## Table of Contents
- [Features](#-features)
- [Requirements](#-requirements)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Troubleshooting](#-troubleshooting)
- [FAQ](#-faq)

## Features

- **Dual Channel Processing**: Independent IN1→OUT1 and IN2→OUT2 signal recording/playback
- **Deep Memory Mode**: High-speed acquisition using Red Pitaya's DMA capabilities
- **Split Trigger Mode**: Isolated trigger handling for each channel
- **Configurable Parameters**: Flexible trigger levels, buffer sizes, and burst patterns
- **Real-time Operation**: Low-latency signal processing with threaded architecture
- **Auto-start**: Automatic startup on Red Pitaya boot

## Overview

This application captures RF signal pulses from Red Pitaya's analog inputs (IN1/IN2) and immediately replays them on the corresponding outputs (OUT1/OUT2). It leverages **Deep Memory Acquisition** for high-speed recording and **Deep Memory Generation** for precise playback.

### How It Works
1. **Acquisition**: Each channel independently monitors its input for trigger conditions
2. **Recording**: When triggered, captures the signal using DMA for minimal latency
3. **Generation**: Immediately replays the captured signal with configurable burst patterns
4. **Loop**: Continues indefinitely until stopped

### ⚠️ Important Notes
- **Not compatible** with Red Pitaya Web Interface simultaneously
- **Requires proper termination** of analog inputs/outputs (50 Ω)
- **Resource intensive** - dedicated real-time signal processing 

## 🔧 Requirements

### Hardware
- **Any Red Pitaya device**
- **Properly terminated** analog inputs/outputs (50 Ω impedance matching)

### Software
- **OS**: Red Pitaya Linux 2.07 or higher
- **Build**: Nightly Build 637 or higher

### ⚠️ Compatibility Warning
This application consumes significant system resources and **cannot run simultaneously** with the Red Pitaya Web Interface. The web interface will be severely slowed down or unresponsive.

Please make sure that Red Pitaya inputs and outputs are properly terminated (matched impedance). Failure to do so may lead to undefined behaviour of the *Record and Playback* application due to the [ringing](https://incompliancemag.com/circuit-theory-model-of-ringing-on-a-transmission-line/) on the [transmission line](https://en.wikipedia.org/wiki/Transmission_line).
Red Pitaya fast analog inputs have input impedance of 1 MΩ. The fast analog outputs have output impedace of 50 Ω.

## Quick Start

1. **Connect** to your Red Pitaya via SSH
2. **Clone** the repository: `git clone https://github.com/RedPitaya/rec_and_play.git`
3. **Enable** running scripts `chmod +x ./rec_and_play/setup.sh`
4. **Run setup**: `cd rec_and_play && ./setup.sh`
5. **Reboot** Red Pitaya
6. **Done!** Application starts automatically on boot

## Installation

### Option A: Automatic Setup (Recommended)

```bash
# 1. Connect via SSH to your Red Pitaya
ssh root@rp-xxxxxx.local

# 2. Download and setup
cd /root
git clone https://github.com/RedPitaya/rec_and_play.git rap
cd rap

# 3. Make scripts executable and run setup
chmod +x setup.sh
./setup.sh

# 4. Reboot Red Pitaya
reboot
```

### Option B: Manual Setup

```bash
# 1. Enable read-write mode
rw

# 2. Copy files to system directory
cp main.py /opt/redpitaya/bin/
cp config.ini /opt/redpitaya/bin/

# 3. Add to startup (optional)
echo "export PYTHONPATH=/opt/redpitaya/lib/python/:\$PYTHONPATH" >> /opt/redpitaya/sbin/startup.sh
echo "/opt/redpitaya/bin/main.py" >> /opt/redpitaya/sbin/startup.sh

# 4. Reboot
reboot
```

### Alternative: Download and Copy

Download the repository to your computer and copy to Red Pitaya:
```bash
scp -r /path-to-downloaded-repository/rec_and_play root@rp-xxxxxx.local:/root
```

## ⚙️ Configuration

The application uses `/opt/redpitaya/bin/config.ini` for all settings. Each channel (ADC/DAC) is configured independently.

### Acquisition Settings (ADC)

| Parameter | Description | Values | Unit |
|-----------|-------------|--------|------|
| `trigger_level` | Voltage threshold for triggering | -1.0 to 1.0 | Volts |
| `trigger_mode` | Trigger condition | `CH1_PE`, `CH1_NE`, `CH2_PE`, `CH2_NE` | - |
| `buffer_time` | Recording duration | 1-30 | µs |

### Generation Settings (DAC)

| Parameter | Description | Values | Unit |
|-----------|-------------|--------|------|
| `signal_source` | Input channel to record | `IN1`, `IN2` | - |
| `count_burst` | Cycles per burst (NCYC) | ≥1 | count |
| `repetition` | Number of bursts (NOR) | ≥1 | count |
| `repetition_delay` | Delay between bursts | ≥ (buffer_time × count_burst + 1) | µs |

### Sample Configuration

```ini
[ADC1]
; IN1 Trigger Level in volts
trigger_level=0.1
; Trigger source (Values: CH1_PE, CH1_NE)
trigger_mode=CH1_PE
; Record signal Buffer size in microseconds (min 1 µs)
buffer_time=20

[ADC2]
; IN2 Trigger Level in volts
trigger_level=0.1
; Trigger source (Values: CH2_PE, CH2_NE)
trigger_mode=CH2_PE
; Record signal Buffer size in microseconds (min 1 µs)
buffer_time=20

[DAC1]
; OUT1 Gen signal from source (IN1, IN2). Which input to use for recording data.
signal_source=IN1
; Number of signal repetitions without delays (NCYC - number of cycles/periods in a single burst).
count_burst=1
; Number of repetitions with delay (NOR - Number of Repetitions/Bursts). Each repetition includes `count_burst` (NCYC) recordings without delay.
repetition=3
; Delay between repetitions.
; If there is a "repetition" number of repetitions, then the minimum allowed delay must be no less than:
; buffer_time * count_burst + 1 µS
; Otherwise the signal may break. If there are no repetitions, the value is ignored
; For example. buffer_time = 20, count_burst=2. repetition_delay = 20 * 2 + 1 = 41 µS
repetition_delay=50

[DAC2]
; OUT2 Gen signal from source (IN1, IN2). Which input to use for recording data.
signal_source=IN2
; Number of signal repetitions without delays (NCYC - number of cycles/periods in a single burst).
count_burst=1
; Number of repetitions with delay (NOR - Number of Repetitions/Bursts). Each repetition includes `count_burst` (NCYC) recordings without delay.
repetition=3
; Delay between repetitions.
; If there is a "repetition" number of repetitions, then the minimum allowed delay must be no less than:
; buffer_time * count_burst + 1 µS
; Otherwise the signal may break. If there are no repetitions, the value is ignored
; For example. buffer_time = 20, count_burst=2. repetition_delay = 20 * 2 + 1 = 41 µS
repetition_delay=50
```

### ⚠️ Configuration Notes
- **Cross-channel routing** is supported but untested
- **Buffer sizes** should be identical for both channels
- **Timing constraints** must be respected to avoid signal corruption

## Usage

### Starting the Application
The application starts automatically on boot if installed with `setup.sh`. For manual start:

```bash
cd /opt/redpitaya/bin
python3 main.py
```

### Monitoring Operation
- Check system logs for status messages
- Use `top` or `htop` to monitor CPU usage
- Application runs indefinitely until interrupted

### Stopping the Application
- **Temporary**: To stop the application until the next boot press `Ctrl+C` in the terminal or kill the process in `top` (write `k` and the PID of the porcess).
    ![Top process](./img/Rec_and_play_top_kill.png)
- **Permanent**: First stop the application. Then remove it from `startup.sh` script located in `/opt/redpitaya/sbin` directory (you may have to enter `rw` mode). Either delete or comment the following lines of code:
    ```
    # Here you can specify commands for autorun at system startup
    export PYTHONPATH=/opt/redpitaya/lib/python/:$PYTHONPATH
    /opt/redpitaya/bin/main.py
    ```
    You can also remove the `main.py` and `config.ini` from `/opt/redpitaya/bin`.

## 🔧 Troubleshooting

### Common Issues

**❌ "Error setting split trigger"**
- Ensure you're using compatible Red Pitaya OS version
- Check system resources aren't exhausted

**❌ "Invalid buffer size"**
- Verify `buffer_time` is between 1-30 µs
- Ensure integer values in configuration

**❌ No signal output**
- Check input signal levels and trigger settings
- Verify proper impedance termination (50 Ω)
- Confirm `signal_source` configuration

**❌ System slowdown**
- This is normal - application uses most system resources
- Web interface will be unresponsive during operation

### Debug Mode
Add print statements to `channel_processing_loop()` for detailed diagnostics.

### Performance Tuning
- Reduce `buffer_time` for faster response
- Adjust `repetition_delay` to prevent signal overlap
- Monitor CPU usage with `top` command
- Reduce the value of `LOOP_DELAY` to achieve faster trigger checking

## ❓ FAQ

**Q: Can I use this with the Web Interface?**  
A: No, this application consumes all processing resources and will make the web interface unresponsive.

**Q: What's the maximum buffer size?**  
A: 30 µs maximum, limited by Red Pitaya's DMA capabilities.

**Q: Can I route IN1 to OUT2?**  
A: Yes, but this configuration is untested. Use `signal_source=IN1` in DAC2 section.

**Q: How do I change trigger sensitivity?**  
A: Adjust `trigger_level` in ADC sections (range: -1.0 to 1.0 Volts).

**Q: Why does the signal break up?**  
A: Usually due to insufficient `repetition_delay`. Ensure it's ≥ (buffer_time × count_burst + 1) µs.

---

**Disclaimer**: This application is for advanced users. Ensure proper RF practices and impedance matching to avoid equipment damage.



