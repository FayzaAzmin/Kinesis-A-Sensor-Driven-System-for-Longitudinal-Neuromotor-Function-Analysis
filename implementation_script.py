import pandas as pd
import numpy as np
import joblib
import json
from scipy.signal import welch

try:
    model = joblib.load('parkinsons_model.pkl')
    scaler = joblib.load('scaler.pkl')
except FileNotFoundError:
    print("CRITICAL ERROR: 'parkinsons_model.pkl' or 'scaler.pkl' not found.")


def _extract_features(raw_window):
    cols = ['Accel_X', 'Accel_Y', 'Accel_Z', 'Gyro_X', 'Gyro_Y', 'Gyro_Z']
    feature_names = [
        'Accel_X_Mean', 'Accel_X_RMS', 'Accel_X_Peak_Freq',
        'Accel_Y_Mean', 'Accel_Y_RMS', 'Accel_Y_Peak_Freq',
        'Accel_Z_Mean', 'Accel_Z_RMS', 'Accel_Z_Peak_Freq',
        'Gyro_X_Mean', 'Gyro_X_RMS', 'Gyro_X_Peak_Freq',
        'Gyro_Y_Mean', 'Gyro_Y_RMS', 'Gyro_Y_Peak_Freq',
        'Gyro_Z_Mean', 'Gyro_Z_RMS', 'Gyro_Z_Peak_Freq'
    ]

    row_features = []
    for col in cols:
        sig = raw_window[col].values
        row_features.append(np.mean(sig))
        row_features.append(np.sqrt(np.mean(sig ** 2)))
        f, p = welch(sig, fs=10.0, nperseg=min(len(sig), 8))
        row_features.append(f[np.argmax(p)])

    return pd.DataFrame([row_features], columns=feature_names)


def _calculate_severity(label, features_df, med_status, stress_level, sleep_status):
    freq = features_df['Accel_X_Peak_Freq'].values[0]
    rms = features_df['Accel_X_RMS'].values[0]

    # Initialize separate placeholders for both UPDRS tracks
    tremor_score = 0
    brady_score = 0

    # 1. Differential Diagnosis Validation
    # If a high physiological frequency is found due to stress/caffeine, it's a non-PD variant
    if freq > 8.0:
        note = "Non-PD Pattern Detected. Peak frequency isolates to Stress, Caffeine, or Physiological variants."
        return 0, 0, note

    # 2. Parallel Unified Parkinson's Rating Scale Evaluation
    # Evaluate resting tremor track
    if label == "Tremor":
        if rms < 0.02:
            tremor_score = 0
        elif rms < 0.10:
            tremor_score = 1
        elif rms < 0.25:
            tremor_score = 2
        elif rms < 0.50:
            tremor_score = 3
        else:
            tremor_score = 4
        # Patient is resting during this task window sequence; tapping is baseline
        brady_score = 0

        # Evaluate bradykinesia tapping track
    elif label == "Tapping":
        if freq >= 2.5:
            brady_score = 0
        elif freq >= 2.0:
            brady_score = 1
        elif freq >= 1.5:
            brady_score = 2
        elif freq >= 1.0:
            brady_score = 3
        else:
            brady_score = 4
        # Patient is actively tapping; not under a resting context evaluation
        tremor_score = 0

    # 3. Multi-Variant Clinical Logic Alerts Mapping
    clinical_flags = []
    if stress_level.upper() == "HIGH":
        clinical_flags.append("High Stress Context")
    if sleep_status.upper() == "DEPRIVED":
        clinical_flags.append("Sleep Deprivation Detected")

    note = f"Meds: {med_status}. Context: {', '.join(clinical_flags) if clinical_flags else 'Baseline'}"

    # Determine active score based on what task was evaluated
    active_score = tremor_score if label == "Tremor" else brady_score

    if med_status.upper() == "ON" and active_score > 1:
        note += " - CRITICAL ALERT: Breakthrough motor systems symptoms detected while fully medicated."
    elif sleep_status.upper() == "DEPRIVED" and active_score >= 2:
        note += " - Clinical Advisory: Pronounced amplitude degradation correlated with systemic fatigue."

    return tremor_score, brady_score, note


def get_parkinsons_report(file_path, med_status="OFF", stress_level="Normal", sleep_status="Good"):
    try:
        df = pd.read_csv(file_path)
        if len(df) < 10:
            return {"Error": "Data payload execution failed. File must contain >= 10 window sequences."}

        window = df.iloc[0:10]
        feat_raw = _extract_features(window)
        feat_scaled = scaler.transform(feat_raw)
        feat_scaled_df = pd.DataFrame(feat_scaled, columns=feat_raw.columns)

        pred = model.predict(feat_scaled_df)[0]

        # Now returns both calculated score elements concurrently
        tremor_score, brady_score, clinical_note = _calculate_severity(
            pred, feat_raw, med_status, stress_level, sleep_status
        )

        raw_metrics = feat_raw.to_dict(orient='records')[0]

        return {
            "Diagnosis": pred,
            "Resting_Tremor_Score": tremor_score,
            "Bradykinesia_Score": brady_score,
            "Clinical_Note": clinical_note,
            "Raw_Metrics": json.dumps(raw_metrics)
        }
    except Exception as e:
        return {"Error": f"Pipeline calculation crash: {str(e)}"}