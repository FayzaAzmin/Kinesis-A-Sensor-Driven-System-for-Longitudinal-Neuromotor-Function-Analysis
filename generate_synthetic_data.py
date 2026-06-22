import pandas as pd
import numpy as np
from scipy.signal import welch
from imblearn.over_sampling import SMOTE

# 1. SETTINGS
files_to_process = [
    ('cleaned_baseline.csv', 'Baseline'),
    ('cleaned_fast_shake.csv', 'Fast_Shake'),
    ('cleaned_slow_shake.csv', 'Slow_Shake'),
    ('cleaned_tapping.csv', 'Tapping'),
    ('cleaned_tremor_shake.csv', 'Tremor')
]
window_size = 10  # 1 second windows (at 10Hz)
step_size = 5     # 0.5 second overlap to get more "seed" samples

# 2. FEATURE EXTRACTION (WINDOWED)
seed_rows = []
print("Creating seed data from windows...")
for file_name, label in files_to_process:
    try:
        df = pd.read_csv(file_name)
        for start in range(0, len(df) - window_size, step_size):
            window = df.iloc[start : start + window_size]
            row_data = {'Label': label}
            for col in ['Accel_X', 'Accel_Y', 'Accel_Z', 'Gyro_X', 'Gyro_Y', 'Gyro_Z']:
                sig = window[col].values
                row_data[f'{col}_Mean'] = np.mean(sig)
                row_data[f'{col}_RMS'] = np.sqrt(np.mean(sig**2))
                # Welch freq
                f, p = welch(sig, fs=10.0, nperseg=min(len(sig), 8))
                row_data[f'{col}_Peak_Freq'] = f[np.argmax(p)]
            seed_rows.append(row_data)
    except FileNotFoundError:
        print(f"File {file_name} not found.")
seed_df = pd.DataFrame(seed_rows)
print(f"Generated {len(seed_df)} seed rows from real recordings.")

# 3. SYNTHETIC GENERATION (SMOTE)
X = seed_df.drop(columns=['Label'])
y = seed_df['Label']

# Define target: We want 100 samples per class (5 classes * 100 = 500 rows)
strategy = {label: 100 for label in seed_df['Label'].unique()}
smote = SMOTE(sampling_strategy=strategy, k_neighbors=3)

X_resampled, y_resampled = smote.fit_resample(X, y)

# 4. SAVE THE FINAL BIG DATASET
final_df = pd.DataFrame(X_resampled, columns=X.columns)
final_df['Label'] = y_resampled
final_df.to_csv('synthetic_master_dataset.csv', index=False)

print(f"\nSuccess! Your dataset now has {len(final_df)} rows.")
print("Saved as 'synthetic_master_dataset.csv'")
