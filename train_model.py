import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import classification_report, accuracy_score
import joblib
# 1. LOAD THE SYNTHETIC DATASET
try:
    df = pd.read_csv('synthetic_master_dataset.csv')
    print("Dataset loaded successfully.")
except FileNotFoundError:
    print("Error: 'synthetic_master_dataset.csv' not found. Please run your SMOTE script first.")
    exit()
# 2. SEPARATE FEATURES AND LABELS
X = df.drop(columns=['Label'])
y = df['Label']
# 3. THE REAL NORMALIZATION (SCALING)
# fit the scaler here and save it so the implementation script
# can "translate" raw data into the same 0-1 range.
scaler = MinMaxScaler()
X_scaled = scaler.fit_transform(X)
# Convert back to DataFrame to keep feature names for the model
X_scaled_df = pd.DataFrame(X_scaled, columns=X.columns)
# 4. SPLIT DATA (80% Train, 20% Test)
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled_df, y, test_size=0.2, random_state=42)
# 5. INITIALIZE AND TRAIN THE RANDOM FOREST
# Using 100 trees to ensure stable predictions
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
# 6. EVALUATE THE MODEL
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"\n--- Training Results ---")
print(f"Overall Accuracy: {accuracy * 100:.2f}%")
print("\nDetailed Classification Report:")
print(classification_report(y_test, y_pred))
# 7. This is for implementation
joblib.dump(model, 'parkinsons_model.pkl')
joblib.dump(scaler, 'scaler.pkl')
print("\nSUCCESS: Model ('parkinsons_model.pkl') and Scaler ('scaler.pkl') have been saved.")
print("You can now run your all-in-one implementation script.")