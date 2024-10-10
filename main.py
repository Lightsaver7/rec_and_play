#!/usr/bin/python3

import configparser
import math
import rp_overlay
import rp
import rp_hw_profiles
import numpy as np

fpga = rp_overlay.overlay()
rp.rp_Init()

base_rate = rp_hw_profiles.rp_HPGetBaseSpeedHzOrDefault()

config = configparser.ConfigParser()
config.read('/opt/redpitaya/bin/config.ini') #path of your .ini file
trigger_level = float(config.get("ADC","trigger_level"))
trigger_mode = config.get("ADC","trigger_mode")
buffer_time = config.get("ADC","buffer_time")
count_burst = config.get("DAC","count_burst")
repetition = config.get("DAC","repetition")
repetition_delay = config.get("DAC","repetition_delay")
gen_src_channel = config.get("DAC","signal_source")
buffer_samples = round((0.000001 * float(buffer_time)) / (1.0 / float(base_rate)))

# Aligin to 128 samples for DAC-AXI mode
buffer_samples = (math.floor(buffer_samples / 128) + 1) * 128

gen_channel = rp.RP_CH_1

acq_trig_sour = rp.RP_TRIG_SRC_CHA_PE
trig_level_sour = rp.RP_T_CH_1
if (trigger_mode == "CH1_PE"):
    acq_trig_sour = rp.RP_TRIG_SRC_CHA_PE
    trig_level_sour = rp.RP_T_CH_1
if (trigger_mode == "CH1_NE"):
    acq_trig_sour = rp.RP_TRIG_SRC_CHA_NE
    trig_level_sour = rp.RP_T_CH_1
if (trigger_mode == "CH2_PE"):
    acq_trig_sour = rp.RP_TRIG_SRC_CHB_PE
    trig_level_sour = rp.RP_T_CH_2
if (trigger_mode == "CH2_NE"):
    acq_trig_sour = rp.RP_TRIG_SRC_CHB_NE
    trig_level_sour = rp.RP_T_CH_2


memory = rp.rp_AcqAxiGetMemoryRegion()
if (memory[0] != rp.RP_OK):
    print("Error get reserved memory")
    exit(1)

dma_start_address = memory[1]
dma_full_size = memory[2]

ch1_dma_address = dma_start_address
ch2_dma_address = (math.floor((dma_start_address + buffer_samples * 2 + 64) / 4096) + 2) * 4096
out1_dma_address = (math.floor((ch2_dma_address + buffer_samples * 2 + 64) / 4096) + 2) * 4096

if (rp.rp_AcqAxiSetDecimationFactor(1) != rp.RP_OK):
    print("Error set decimation")
    exit(1)

if (rp.rp_AcqAxiSetTriggerDelay(rp.RP_CH_1,buffer_samples) != rp.RP_OK):
    print("Error set trigger delay")
    exit(1)

if (rp.rp_AcqAxiSetTriggerDelay(rp.RP_CH_2,buffer_samples) != rp.RP_OK):
    print("Error set trigger delay")
    exit(1)

if (rp.rp_AcqAxiSetBufferSamples(rp.RP_CH_1,ch1_dma_address, buffer_samples) != rp.RP_OK):
    print("Error setting address for DMA mode for CH1")
    exit(1)

if (rp.rp_AcqAxiSetBufferSamples(rp.RP_CH_2,ch2_dma_address, buffer_samples) != rp.RP_OK):
    print("Error setting address for DMA mode for CH2")
    exit(1)

if (rp.rp_AcqAxiEnable(rp.RP_CH_1,True) != rp.RP_OK):
    print("Error enable axi mode for CH1")
    exit(1)

if (rp.rp_AcqAxiEnable(rp.RP_CH_2,True) != rp.RP_OK):
    print("Error enable axi mode for CH2")
    exit(1)

if (rp.rp_GenAxiReserveMemory(rp.RP_CH_1,out1_dma_address, out1_dma_address + buffer_samples * 2) != rp.RP_OK):
    print("Error setting address for DMA mode for OUT1")
    exit(1)

if (rp.rp_GenAxiSetDecimationFactor(rp.RP_CH_1,1) != rp.RP_OK):
    print("Error setting decimation for generator")
    exit(1)

if (rp.rp_GenAxiSetEnable(rp.RP_CH_1,True) != rp.RP_OK):
    print("Error enable axi mode for OUT1")
    exit(1)

arr_f_ch1 = np.zeros(buffer_samples, dtype=np.float32)
arr_f_ch2 = np.zeros(buffer_samples, dtype=np.float32)

rp.rp_GenSetAmplitudeAndOffsetOrigin(rp.RP_CH_1)
rp.rp_GenMode(rp.RP_CH_1, rp.RP_GEN_MODE_BURST)
rp.rp_GenBurstCount(rp.RP_CH_1, int(count_burst))
rp.rp_GenBurstRepetitions(rp.RP_CH_1, int(repetition));
rp.rp_GenBurstPeriod(rp.RP_CH_1, int(repetition_delay));

while(1):
    if (rp.rp_AcqSetTriggerLevel(trig_level_sour,trigger_level) != rp.RP_OK):
        print("Error set trigger level")
        exit(1)

    if (rp.rp_AcqStart() != rp.RP_OK):
        print("Error start acq")
        exit(1)

    rp.rp_AcqSetTriggerSrc(acq_trig_sour)

    # Trigger state
    while 1:
        trig_state = rp.rp_AcqGetTriggerState()[1]
        if trig_state == rp.RP_TRIG_STATE_TRIGGERED:
            break

    # Fill state
    while 1:
        if rp.rp_AcqGetBufferFillState()[1]:
            break
    rp.rp_AcqStop()
    tp=rp.rp_AcqGetWritePointerAtTrig()[1]
    rp.rp_AcqGetDataVNP(rp.RP_CH_1,tp, arr_f_ch1)
    rp.rp_AcqGetDataVNP(rp.RP_CH_2,tp, arr_f_ch2)

    # Pass data to generator
    if (gen_src_channel == "IN1"):
        rp.rp_GenAxiWriteWaveform(gen_channel,arr_f_ch1)

    if (gen_src_channel == "IN2"):
        rp.rp_GenAxiWriteWaveform(gen_channel,arr_f_ch2)

    rp.rp_GenOutEnable(gen_channel);
    rp.rp_GenTriggerOnly(gen_channel);
