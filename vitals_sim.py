import time
import wfdb
import random

# Load ECG record from PhysioNet data in 'mitdb'
record = wfdb.rdrecord('100', pn_dir='mitdb')

# Loop through each ECG sample and simulate vitals
for val in record.p_signal:
    heart_rate = random.randint(60, 100)      # bpm
    spo2 = random.randint(95, 99)             # %
    bp_sys = random.randint(110, 130)         # mmHg
    bp_dia = random.randint(70, 85)           # mmHg

    print(f"HR: {heart_rate} bpm | SpO₂: {spo2}% | BP: {bp_sys}/{bp_dia} mmHg")
    time.sleep(1)  # 1-second updates
