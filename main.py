#!/usr/bin/python3

import configparser
import math
import threading
import time
import numpy as np
import rp_overlay
import rp
import rp_hw_profiles

# Constants
ALIGNMENT_SIZE = 128
DMM_ALIGNMENT_SIZE = 4096
CONFIG_PATH = '/opt/redpitaya/bin/config.ini'
DECIMATION_FACTOR = 1
MEMORY_ALIGNMENT_OFFSET = 64
LOOP_DELAY = 0.001  # Delay in seconds for main loop to prevent CPU overload

def calculate_aligned_address(base_addr, size, alignment=DMM_ALIGNMENT_SIZE):
    """Calculate DMA address with proper alignment"""
    return ((base_addr + size + MEMORY_ALIGNMENT_OFFSET) // alignment + 2) * alignment

def validate_config(config):
    """Validate configuration values"""
    required_sections = ['ADC1', 'ADC2', 'DAC1', 'DAC2']
    for section in required_sections:
        if not config.has_section(section):
            raise ValueError(f"Missing configuration section: {section}")

        if section in ['ADC1', 'ADC2']:
            # Validate ADC parameters
            if not config[section].get('trigger_mode'):
                raise ValueError(f"Missing trigger_mode in {section}")
            if not config[section].get('trigger_level'):
                raise ValueError(f"Missing trigger_level in {section}")
            if not config[section].get('buffer_time'):
                raise ValueError(f"Missing buffer_time in {section}")
            # Validate critical parameters
            if int(config[section]['buffer_time']) <= 0:
                raise ValueError(f"Invalid buffer_time in {section}")
            if float(config[section]['trigger_level']) < -1 or float(config[section]['trigger_level']) > 1:
                raise ValueError(f"Invalid trigger_level in {section}: must be between -1 and 1")
        elif section in ['DAC1', 'DAC2']:
            # Validate DAC parameters
            if not config[section].get('signal_source'):
                raise ValueError(f"Missing signal_source in {section}")
            if not config[section].get('count_burst'):
                raise ValueError(f"Missing count_burst in {section}")
            if not config[section].get('repetition'):
                raise ValueError(f"Missing repetition in {section}")
            if not config[section].get('repetition_delay'):
                raise ValueError(f"Missing repetition_delay in {section}")
            # Validate critical parameters
            if int(config[section]['count_burst']) <= 0:
                raise ValueError(f"Invalid count_burst in {section}")
            if int(config[section]['repetition']) <= 0:
                raise ValueError(f"Invalid repetition in {section}")
            if float(config[section]['repetition_delay']) < 0:
                raise ValueError(f"Invalid repetition_delay in {section}")

def setup_channel_trigger(channel_data, ch_num):
    """Setup trigger configuration for a channel"""
    ch_key = f'ADC{ch_num}'
    mode = channel_data[ch_key]['trigger_mode']

    # Default values
    acq_trig_sour = rp.RP_TRIG_SRC_CHA_PE
    trig_level_sour = rp.RP_T_CH_1

    if mode == "CH1_PE":
        acq_trig_sour = rp.RP_TRIG_SRC_CHA_PE
        trig_level_sour = rp.RP_T_CH_1
    elif mode == "CH1_NE":
        acq_trig_sour = rp.RP_TRIG_SRC_CHA_NE
        trig_level_sour = rp.RP_T_CH_1
    elif mode == "CH2_PE":
        acq_trig_sour = rp.RP_TRIG_SRC_CHB_PE
        trig_level_sour = rp.RP_T_CH_2
    elif mode == "CH2_NE":
        acq_trig_sour = rp.RP_TRIG_SRC_CHB_NE
        trig_level_sour = rp.RP_T_CH_2

    return {
        'acq_trig_sour': acq_trig_sour,
        'trig_level_sour': trig_level_sour
    }

# Load FPGA and init Python API commands
fpga = rp_overlay.overlay()
rp.rp_Init()

base_rate = rp_hw_profiles.rp_HPGetBaseSpeedHzOrDefault()

# Get configuration settings from config.ini file
config = configparser.ConfigParser()
try:
    config.read(CONFIG_PATH)
    validate_config(config)
except Exception as e:
    print(f"Configuration error: {e}")
    exit(1)

# Channel configurations - load data for both channels
channels = ['ADC1', 'ADC2', 'DAC1', 'DAC2']
channel_num = [rp.RP_CH_1, rp.RP_CH_2]
trigger_pointer = [0, 0]
channel_data = {}

for ch in channels:
    section = config[ch]
    if ch.startswith('ADC'):
        # ADC channels
        channel_data[ch] = {
            'trigger_level': float(section['trigger_level']),
            'trigger_mode': section['trigger_mode'],
            'buffer_time': int(section['buffer_time']),             # Keep as int
            'count_burst': 0,                                       # Not used for ADC
            'repetition': 0,                                        # Not used for ADC
            'repetition_delay': 0,                                  # Not used for ADC
            'gen_src_channel': None                                 # No generation source for ADC
        }
    else:
        # DAC channels
        channel_data[ch] = {
            'trigger_level': 0.0,                                   # Not used for DAC
            'trigger_mode': 'NONE',                                 # Not used for DAC
            'buffer_time': 0,                                       # Not used for DAC
            'count_burst': int(section['count_burst']),
            'repetition': int(section['repetition']),
            'repetition_delay': int(section['repetition_delay']),
            'gen_src_channel': section.get('signal_source', 'IN1')  # Default to IN1 if not specified
    }

# Calculate buffer samples for both channels
for ch in ['ADC1', 'ADC2']:
    buffer_time_us = int(channel_data[ch]['buffer_time'])
    # Use integer arithmetic for precision: (buffer_time_us * base_rate) / 1_000_000
    buffer_samples = (buffer_time_us * base_rate) // 1_000_000
    # Align to 128 samples for DAC-AXI mode using ceiling division
    buffer_samples = ((buffer_samples + ALIGNMENT_SIZE - 1) // ALIGNMENT_SIZE) * ALIGNMENT_SIZE

    if buffer_samples <= 0:
        raise ValueError(f"Invalid buffer size {buffer_samples} for {ch}")

    channel_data[ch]['buffer_samples'] = buffer_samples

# Calculate buffer samples for DAC channels (use corresponding ADC buffer size)
for ch in ['DAC1', 'DAC2']:
    adc_ch = ch.replace('DAC', 'ADC')
    channel_data[ch]['buffer_samples'] = channel_data[adc_ch]['buffer_samples']

# Trigger configuration for both channels
trigger_config = {}
for ch_num in [1, 2]:
    trigger_config[ch_num] = setup_channel_trigger(channel_data, ch_num)

# Split trigger mode
if (rp.rp_AcqSetSplitTrigger(True) != rp.RP_OK):
    print("Error setting split trigger")
    exit(1)

# Reset specific channels
for i in range(len(channel_num)):
    if (rp.rp_AcqResetCh(channel_num[i]) != rp.RP_OK):
        print(f"Error reseting channel {channel_num[i]}")
        exit(1)



# Configure Deep Memory Acquisition
memory = rp.rp_AcqAxiGetMemoryRegion()
if (memory[0] != rp.RP_OK):
    print("Error get reserved memory")
    exit(1)

dma_start_address = memory[1]
dma_full_size = memory[2]

# Calculate DMA addresses with proper alignment
ch1_dma_address = dma_start_address
ch2_dma_address = calculate_aligned_address(dma_start_address,
                                          channel_data['ADC1']['buffer_samples'] * 2)
out1_dma_address = calculate_aligned_address(ch2_dma_address,
                                           channel_data['ADC2']['buffer_samples'] * 2)
out2_dma_address = calculate_aligned_address(out1_dma_address,
                                           channel_data['DAC1']['buffer_samples'] * 2)



# Setup channels with improved error handling
def setup_acquisition_channel(ch, buffer_samples, dma_address):
    """Setup a single acquisition channel"""
    errors = []

    # Set decimation
    if rp.rp_AcqAxiSetDecimationFactorCh(ch, DECIMATION_FACTOR) != rp.RP_OK:
        errors.append(f"decimation for {ch}")

    # Set trigger delay
    if rp.rp_AcqAxiSetTriggerDelay(ch, buffer_samples) != rp.RP_OK:
        errors.append(f"trigger delay for {ch}")

    # Set buffer samples
    if rp.rp_AcqAxiSetBufferSamples(ch, dma_address, buffer_samples) != rp.RP_OK:
        errors.append(f"buffer samples for {ch}")

    # Enable AXI mode
    if rp.rp_AcqAxiEnable(ch, True) != rp.RP_OK:
        errors.append(f"AXI enable for {ch}")

    if errors:
        print(f"Errors setting up acquisition channel {ch}: {', '.join(errors)}")
        return False
    return True

def setup_generation_channel(ch, dma_address, buffer_samples):
    """Setup a single generation channel"""
    errors = []

    # Reserve memory
    if rp.rp_GenAxiReserveMemory(ch, dma_address, dma_address + buffer_samples * 2) != rp.RP_OK:
        errors.append(f"memory reservation for {ch}")

    # Set decimation
    if rp.rp_GenAxiSetDecimationFactor(ch, DECIMATION_FACTOR) != rp.RP_OK:
        errors.append(f"decimation for {ch}")

    # Enable AXI mode
    if rp.rp_GenAxiSetEnable(ch, True) != rp.RP_OK:
        errors.append(f"AXI enable for {ch}")

    if errors:
        print(f"Errors setting up generation channel {ch}: {', '.join(errors)}")
        return False
    return True

# Setup acquisition channels
for i, ch in enumerate(channel_num):
    adc_ch = f'ADC{i+1}'
    if not setup_acquisition_channel(ch,
                                   channel_data[adc_ch]['buffer_samples'],
                                   [ch1_dma_address, ch2_dma_address][i]):
        exit(1)

# Set trigger levels
for i, ch in enumerate(channel_num):
    adc_ch = f'ADC{i+1}'
    if rp.rp_AcqSetTriggerLevel(trigger_config[i+1]['trig_level_sour'],
                                channel_data[adc_ch]['trigger_level']) != rp.RP_OK:
        print(f"Error set trigger level for channel {adc_ch}")
        exit(1)

# Setup generation channels
if not setup_generation_channel(rp.RP_CH_1, out1_dma_address, channel_data['DAC1']['buffer_samples']):
    exit(1)
if not setup_generation_channel(rp.RP_CH_2, out2_dma_address, channel_data['DAC2']['buffer_samples']):
    exit(1)

# Initialize data arrays
arr_f_ch1 = np.zeros(channel_data['ADC1']['buffer_samples'], dtype=np.float32)
arr_f_ch2 = np.zeros(channel_data['ADC2']['buffer_samples'], dtype=np.float32)

# Setup generator parameters for both channels
for i, ch in enumerate(channel_num):
    dac_ch = f'DAC{i+1}'

    # Set amplitude and offset
    if (rp.rp_GenSetAmplitudeAndOffsetOrigin(ch) != rp.RP_OK):
        print(f"Error setting amplitude and offset for channel {ch}")
        exit(1)

    # Set burst mode
    if (rp.rp_GenMode(ch, rp.RP_GEN_MODE_BURST) != rp.RP_OK):
        print(f"Error setting burst mode for channel {ch}")
        exit(1)

    # Configure burst parameters
    if (rp.rp_GenBurstCount(ch, channel_data[dac_ch]['count_burst']) != rp.RP_OK):
        print(f"Error setting burst count for channel {ch}")
        exit(1)
    if (rp.rp_GenBurstRepetitions(ch, channel_data[dac_ch]['repetition']) != rp.RP_OK):
        print(f"Error setting burst repetitions for channel {ch}")
        exit(1)
    if (rp.rp_GenBurstPeriod(ch, int(channel_data[dac_ch]['repetition_delay'])) != rp.RP_OK):
        print(f"Error setting burst period for channel {ch}")
        exit(1)

def process_channel_data(channel_idx, trigger_pointer):
    """Process acquired data for a single channel and prepare for generation"""
    ch = channel_num[channel_idx]
    dac_ch = f'DAC{channel_idx+1}'

    # Direct array access without intermediate variables
    if channel_idx == 0:
        if rp.rp_AcqGetDataVNP(ch, trigger_pointer, arr_f_ch1) != rp.RP_OK:
            print(f"Error acquiring data for channel {ch}")
            return
        waveform_data = arr_f_ch1
    else:
        if rp.rp_AcqGetDataVNP(ch, trigger_pointer, arr_f_ch2) != rp.RP_OK:
            print(f"Error acquiring data for channel {ch}")
            return
        waveform_data = arr_f_ch2

    # Basic data validation (check for NaN/inf values)
    if np.any(~np.isfinite(waveform_data)):
        print(f"Invalid data detected in channel {ch} (NaN/inf values)")
        return

    # Determine source more efficiently
    gen_src = channel_data[dac_ch]['gen_src_channel']
    if gen_src == "IN2" and channel_idx == 0:  # Cross-channel case
        waveform_data = arr_f_ch2
    # Default: use same channel (already set above)

    # Write waveform (ensure API supports async if possible)
    if rp.rp_GenAxiWriteWaveform(ch, waveform_data) != rp.RP_OK:
        print(f"Error writing waveform for channel {ch}")
        return

    # Enable and trigger generation
    rp.rp_GenOutEnable(ch)
    rp.rp_GenTriggerOnly(ch)

def channel_processing_loop(channel_idx):
    """Main processing loop for a single channel - runs independently"""
    ch = channel_num[channel_idx]
    adc_ch = f'ADC{channel_idx+1}'
    dac_ch = f'DAC{channel_idx+1}'

    print(f"Starting independent processing loop for channel {channel_idx+1}")

    try:
        while not stop_threads:
            # Start acquisition for this channel
            if rp.rp_AcqStartCh(ch) != rp.RP_OK:
                print(f"Error starting acquisition for channel {ch}")
                break

            # Set trigger source for this channel
            trigger_src = trigger_config[channel_idx+1]['acq_trig_sour']
            if rp.rp_AcqSetTriggerSrcCh(ch, trigger_src) != rp.RP_OK:
                print(f"Error setting trigger source for channel {ch}")
                break

            # Wait for trigger on this channel
            while not stop_threads:
                trig_state = rp.rp_AcqGetTriggerStateCh(ch)[1]
                if trig_state == rp.RP_TRIG_STATE_TRIGGERED:
                    break
                # Small delay between cycles to prevent overwhelming the system
                time.sleep(LOOP_DELAY)

            if stop_threads:
                break

            # Wait for buffer to fill on this channel
            while not stop_threads:
                if rp.rp_AcqGetBufferFillStateCh(ch)[1]:
                    break
                # No sleep - tight loop for minimal latency

            if stop_threads:
                break

            # Stop acquisition and process data for this channel
            rp.rp_AcqStopCh(ch)
            trigger_pointer = rp.rp_AcqGetWritePointerAtTrigCh(ch)[1]
            process_channel_data(channel_idx, trigger_pointer)

    except Exception as e:
        print(f"Error in channel {channel_idx+1} processing loop: {e}")
    finally:
        # Cleanup for this channel
        rp.rp_AcqStopCh(ch)
        rp.rp_GenOutDisable(ch)
        print(f"Channel {channel_idx+1} processing stopped")


# Start the infinite loop of recording and generating
print("Starting real-time signal processing loop...")
print("Press Ctrl+C to stop")

# Global stop condition for threads
stop_condition = threading.Condition()
stop_threads = False

# Create and start threads for each channel
threads = []
for i in range(len(channel_num)):
    thread = threading.Thread(target=channel_processing_loop, args=(i,))
    thread.daemon = True                        # Threads will exit when main program exits
    threads.append(thread)
    thread.start()

try:
    # Keep main thread alive with efficient blocking wait
    with stop_condition:
        stop_condition.wait()                   # Efficient blocking wait instead of polling
except KeyboardInterrupt:
    print("\nStopping signal processing...")
    with stop_condition:
        stop_threads = True
        stop_condition.notify_all()

    # Wait for all threads to finish
    for thread in threads:
        thread.join(timeout=5.0)

except Exception as e:
    print(f"Error in main thread: {e}")
    with stop_condition:
        stop_threads = True
        stop_condition.notify_all()
finally:
    # Cleanup
    print("Cleaning up resources...")
    with stop_condition:
        stop_threads = True
        stop_condition.notify_all()
    for thread in threads:
        thread.join(timeout=2.0)

    rp.rp_Release()
    print("Done.")

