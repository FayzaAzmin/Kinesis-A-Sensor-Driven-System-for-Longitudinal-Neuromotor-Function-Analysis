import pandas as pd
import numpy as np
from scipy.signal import butter, filtfilt


# --- 1. Define Filter Functions ---
def butter_bandpass(lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a


def butter_bandpass_filter(data, lowcut, highcut, fs, order=4):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = filtfilt(b, a, data)
    return y


# --- 2. Configuration ---
sampling_rate = 10.0  # 10 Hz
low_freq = 2.0  # 2 Hz
high_freq = 4.5  # 4.5 Hz

# List of all the CSV files to process
files_to_clean = [
    'baseline.csv',
    'fast_shake.csv',
    'slow_shake.csv',
    'tapping.csv',
    'tremor_shake.csv'
]


# --- 3. Process All Files in a Loop ---
def process_all_files():
    print("Starting batch processing...\n")

    for file_name in files_to_clean:
        try:
            print(f"--> Processing: {file_name}")

            # A. Load the raw data
            df = pd.read_csv(file_name)

            # B. Clean basic anomalies
            df_cleaned = df.dropna().copy()

            # Remove initialization noise (first 20 rows = 2 seconds at 10 Hz)
            if len(df_cleaned) > 20:
                df_cleaned = df_cleaned.iloc[20:].copy()

            df_cleaned.reset_index(drop=True, inplace=True)

            # C. Apply the bandpass filter
            df_filtered = df_cleaned.copy()
            for col in ['Accel_X', 'Accel_Y', 'Accel_Z', 'Gyro_X', 'Gyro_Y', 'Gyro_Z']:
                if col in df_filtered.columns:
                    df_filtered[col] = butter_bandpass_filter(
                        df_cleaned[col].values,
                        lowcut=low_freq,
                        highcut=high_freq,
                        fs=sampling_rate,
                        order=4
                    )
            # D. Save the cleaned data to a new file
            output_file = f"cleaned_{file_name}"
            df_filtered.to_csv(output_file, index=False)
            print(f"    Saved: {output_file}\n")

        except FileNotFoundError:
            print(f"    Error: Could not find '{file_name}'. Ensure it is in the same folder.\n")
        except Exception as e:
            print(f"    Error processing '{file_name}': {e}\n")

    print("Batch processing complete!")
# --- 4. Run the Script ---
if __name__ == "__main__":
    process_all_files()