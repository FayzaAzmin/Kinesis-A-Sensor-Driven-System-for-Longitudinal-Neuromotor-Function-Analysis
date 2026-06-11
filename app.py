import csv
import io
import os
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, Response, flash
from werkzeug.utils import secure_filename
from models import db, User, Telemetry

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'kinesis_secure_deployment_token'

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/profile_pics')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

db.init_app(app)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def check_password_policy(password):
    if len(password) < 8:
        return False
    if not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[0-9!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True


# ==========================================
# AUTH REGISTRATION PORTALS
# ==========================================

@app.route("/", methods=['GET', 'POST'])
@app.route("/login", methods=['GET', 'POST'])
def login():
    if "username" in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            session["username"] = user.username
            session["role"] = user.role
            return redirect(url_for('dashboard'))
        flash("Invalid Clinical Credentials. Please try again.", "danger")
        return redirect(url_for('login'))
    return render_template("login.html")


@app.route("/signup", methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")
        age = request.form.get("age")
        gender = request.form.get("gender")
        mobile_number = request.form.get('full_mobile_number')

        if User.query.filter_by(username=username).first():
            flash("Username already registered in system database.", "danger")
            return redirect(url_for('signup'))

        if not check_password_policy(password):
            flash(
                "Password must contain uppercase, lowercase, special signs/numbers, and be 8 characters long.",
                "danger")
            return redirect(url_for('signup'))

        new_user = User(
            username=username, email=email, password=password, role=role,
            age=int(age) if age else None, gender=gender, mobile_number=mobile_number
        )
        if role == 'patient':
            new_user.unique_patient_id = User.generate_patient_id()

        db.session.add(new_user)
        db.session.commit()
        flash("Account created successfully! Please log in below.", "success")
        return redirect(url_for('login'))
    return render_template("signup.html")


@app.route("/forgot-password", methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get("username")
        new_password = request.form.get("new_password")

        if not check_password_policy(new_password):
            flash("Password must contain uppercase, lowercase, special signs/numbers, and be 8 characters long",
                  "danger")
            return redirect(url_for('forgot_password'))

        user = User.query.filter_by(username=username).first()
        if not user:
            flash(f'User "{username}" does not exist.', "danger")
            return redirect(url_for('forgot_password'))
        user.password = new_password
        db.session.commit()
        flash("Password updated successfully!", "success")
        return redirect(url_for('login'))
    return render_template("forgot_password.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))


# ==========================================
# RESOURCE AVATAR MANAGEMENT
# ==========================================

@app.route("/upload-avatar", methods=['POST'])
def upload_avatar():
    if "username" not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session["username"]).first()
    if not user:
        return redirect(url_for('login'))
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file and allowed_file(file.filename):
            if user.profile_pic != 'default.png':
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], user.profile_pic)
                if os.path.exists(old_path):
                    os.remove(old_path)
            filename = secure_filename(f"{user.username}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            user.profile_pic = filename
            db.session.commit()
            flash("Profile picture updated successfully!", "success")
    return redirect(url_for('dashboard'))


@app.route("/remove-avatar")
def remove_avatar():
    if "username" not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session["username"]).first()
    if user and user.profile_pic != 'default.png':
        old_path = os.path.join(app.config['UPLOAD_FOLDER'], user.profile_pic)
        if os.path.exists(old_path):
            os.remove(old_path)
        user.profile_pic = 'default.png'
        db.session.commit()
        flash("Profile avatar removed, reset to default view.", "info")
    return redirect(url_for('dashboard'))


# ==========================================
# MANUAL PHYSIOLOGICAL FACTOR SUBMISSION
# ==========================================

@app.route("/submit-physiological-factors", methods=['POST'])
def submit_physiological_factors():
    if "username" not in session or session.get("role") != 'patient':
        return redirect(url_for('login'))

    med_status = request.form.get("med_status", default="OFF")
    stress_level = request.form.get("stress_level", default="Normal")
    sleep_deprived = request.form.get("sleep_deprived") == "True"

    latest_log = Telemetry.query.filter_by(patient_username=session["username"]).order_by(
        Telemetry.timestamp.desc()).first()

    tremor_val = latest_log.resting_tremor_score if latest_log else 0
    brady_val = latest_log.bradykinesia_score if latest_log else 0

    new_log = Telemetry(
        patient_username=session["username"],
        resting_tremor_score=tremor_val,
        bradykinesia_score=brady_val,
        med_status=med_status,
        stress_level=stress_level,
        sleep_deprived=sleep_deprived,
        dominant_frequency_hz=4.5 if tremor_val > 0 else 0.0,
        signal_amplitude_rms=0.015 * tremor_val,
        spectral_entropy=0.85
    )
    db.session.add(new_log)
    db.session.commit()
    flash("Physiological baseline context updated seamlessly!", "success")
    return redirect(url_for('dashboard'))


# ==========================================
# AUTOMATED HARDWARE STREAM RECEIVER (API)
# ==========================================

@app.route('/api/v1/sensor-stream', methods=['POST'])
def handle_sensor_stream():
    patient_username = request.headers.get('X-Patient-Username')
    if not patient_username:
        return jsonify({"status": "error", "message": "Missing authentication identifier header"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "Payload block empty"}), 400

    sensor_data = data.get("sensor_data", [])
    if not sensor_data:
        return jsonify({"status": "error", "message": "No IMU batch arrays present"}), 400

    # 📊 DSP Math Processing Tiers (Calculated from incoming telemetry frame batches)
    accel_magnitudes = [(f['Accel_X'] ** 2 + f['Accel_Y'] ** 2 + f['Accel_Z'] ** 2) ** 0.5 for f in sensor_data]
    avg_magnitude = sum(accel_magnitudes) / len(accel_magnitudes)

    # 1. Tremor Score Calculation (0-4 adaptive grading based on total raw movement force)
    calculated_tremor_score = min(4, int(avg_magnitude * 2))

    # 2. Dynamic Tapping / Bradykinesia Score Calculation (0-4 Adaptive Grading)
    speed_deltas = [abs(accel_magnitudes[i] - accel_magnitudes[i - 1]) for i in range(1, len(accel_magnitudes))]
    avg_velocity_delta = sum(speed_deltas) / len(speed_deltas) if speed_deltas else 0

    if calculated_tremor_score > 1:
        # If active high involuntary tremors are present, reset voluntary tapping score
        calculated_brady_score = 0
    else:
        # Evaluate velocity fluctuations against calibrated movement boundaries
        if avg_velocity_delta < 0.15:
            calculated_brady_score = 4  # Frozen / extreme sluggish movement latency
        elif avg_velocity_delta < 0.35:
            calculated_brady_score = 3
        elif avg_velocity_delta < 0.65:
            calculated_brady_score = 2
        elif avg_velocity_delta < 1.10:
            calculated_brady_score = 1  # Mild deceleration or rhythmic variations
        else:
            calculated_brady_score = 0  # High-tempo, consistent crisp voluntary tapping cycles

    new_telemetry_entry = Telemetry(
        patient_username=patient_username,
        resting_tremor_score=calculated_tremor_score,
        bradykinesia_score=calculated_brady_score,
        med_status=data.get("med_status", "OFF"),
        stress_level=data.get("stress_level", "Normal"),
        sleep_deprived=(data.get("sleep_status") == "Poor"),
        dominant_frequency_hz=4.8 if calculated_tremor_score > 0 else 0.0,
        signal_amplitude_rms=round(avg_magnitude * 0.01, 4),
        spectral_entropy=0.79
    )

    try:
        db.session.add(new_telemetry_entry)
        db.session.commit()
        print(f"[STREAM INGEST] Stored 10-frame hardware batch for user '{patient_username}' successfully.")
        return jsonify({"status": "success", "message": "Kinesis pipeline storage synced safely"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"[DATABASE ERROR] Ingest transaction rolled back: {e}")
        return jsonify({"status": "error", "message": "Database write rejection event"}), 500


# ==========================================
# PATIENT-ONLY ASYNCHRONOUS LIVE TELEMETRY API
# ==========================================

@app.route('/api/telemetry/live')
def live_telemetry_api():
    if "username" not in session:
        return jsonify({"status": "error", "message": "Unauthorized session context"}), 401

    # SECURITY POLICY: Real-time dynamic parsing is restricted strictly to patients
    if session.get("role") != 'patient':
        return jsonify({"status": "error", "message": "Real-time stream interface restricted to patients"}), 403

    # Fetch last 15 entries for the patient stream canvas layout
    latest_records = Telemetry.query.filter_by(patient_username=session["username"]).order_by(
        Telemetry.timestamp.desc()).limit(15).all()
    latest_records.reverse()  # Order chronologically for left-to-right plotting

    return jsonify({
        "timestamps": [r.timestamp.strftime('%H:%M:%S') for r in latest_records],
        "tremor_scores": [r.resting_tremor_score for r in latest_records],
        "bradykinesia_scores": [r.bradykinesia_score for r in latest_records],
        "current_tremor": latest_records[-1].resting_tremor_score if latest_records else 0,
        "current_brady": latest_records[-1].bradykinesia_score if latest_records else 0
    })
@app.route('/api/v1/write-active-user', methods=['POST'])
def write_active_user():
    data = request.get_json()
    username = data.get("username")
    if username:
        with open("active_user.txt", "w") as f:
            f.write(username)
    return jsonify({"status": "synchronized"}), 200


# ==========================================
# CORE EXECUTIVE DASHBOARD ENGINE
# ==========================================

@app.route("/dashboard", methods=['GET', 'POST'])
def dashboard():
    if "username" not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session["username"]).first()
    if not user:
        session.clear()
        return redirect(url_for('login'))

    target_patient = None
    patient_metadata = None
    current_pid = request.form.get('patient_id') or request.args.get('patient_id') or ""

    if user.role == 'patient':
        target_patient = user.username
        current_pid = user.unique_patient_id
    elif user.role in ['caregiver', 'clinician']:
        if current_pid:
            matched_patient = User.query.filter_by(unique_patient_id=current_pid, role='patient').first()
            if matched_patient:
                target_patient = matched_patient.username
                patient_metadata = matched_patient
            else:
                flash("Incorrect Patient Identification Alphanumeric Key.", "danger")
                current_pid = ""

    records = []
    status_text = "HEALTH STATUS VERIFICATION PENDING"
    suggestion_text = "No sensor telemetry records received within the system data pipeline yet."

    if target_patient:
        records = Telemetry.query.filter_by(patient_username=target_patient).order_by(Telemetry.timestamp.asc()).all()

        if records:
            avg_tremor = sum(r.resting_tremor_score for r in records) / len(records)
            avg_brady = sum(r.bradykinesia_score for r in records) / len(records)

            if avg_tremor > 1.0 or avg_brady > 1.0:
                status_text = "UNHEALTHY SYSTEM FLAG OBSERVED"
                suggestion_text = "Anomalous motor fluctuations detected outside baseline tolerances. We highly recommend consulting a certified clinical doctor or health professional for a checkup."
            else:
                status_text = "HEALTHY SYSTEM STATUS APPROVED"
                suggestion_text = "Calculated oscillations and voluntary motor rhythms are stable and within safe operating parameters."

    timestamps = [r.timestamp.strftime("%Y-%m-%d %H:%M") for r in records] if records else []
    tremor_scores = [r.resting_tremor_score for r in records] if records else []
    brady_scores = [r.bradykinesia_score for r in records] if records else []

    return render_template(
        "dashboard.html", user=user, records=records, target_patient=target_patient,
        patient_metadata=patient_metadata, timestamps=timestamps, tremor_scores=tremor_scores,
        bradykinesia_scores=brady_scores, status_text=status_text, suggestion_text=suggestion_text,
        current_pid=current_pid
    )


@app.route("/export/summary/<username>")
def export_summary(username):
    if "username" not in session:
        return redirect(url_for('login'))

    current_user_role = session.get("role")
    query = Telemetry.query.filter_by(patient_username=username)
    records = query.all()
    output = io.StringIO()

    output.write(f"KINESIS CLINICAL METRIC EXPORT FOR PATIENT: {username}\n")
    output.write(f"Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")
    output.write(f"Access Authorization Level: {current_user_role.upper()}\n")
    output.write("=" * 90 + "\n\n")

    if not records:
        output.write("No operational system telemetry data streams recorded for this profile yet.\n")

    elif current_user_role == 'clinician':
        output.write(
            f"{'TIMESTAMP (UTC)':<26} | {'TREMOR (0-4)':<12} | {'TAP SCORE':<10} | {'FREQ (Hz)':<10} | {'AMP (RMS)':<10} | {'ENTROPY':<8}\n")
        output.write("-" * 90 + "\n")
        for r in records:
            output.write(
                f"{r.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f'):<26} | "
                f"{r.resting_tremor_score:<12} | "
                f"{r.bradykinesia_score:<10} | "
                f"{r.dominant_frequency_hz:<10.2f} | "
                f"{r.signal_amplitude_rms:<10.4f} | "
                f"{r.spectral_entropy:<8.3f}\n"
            )

    else:
        output.write(
            f"{'RECORD TIME':<17} | {'TREMOR':<8} | {'TAP SPEED':<10} | {'MED STATE':<10} | {'STRESS LEVEL':<14} | {'SLEEP DEPRIVED'}\n")
        output.write("-" * 90 + "\n")
        for r in records:
            output.write(
                f"{r.timestamp.strftime('%Y-%m-%d %H:%M'):<17} | "
                f"{r.resting_tremor_score}/4{' ':<5} | "
                f"{r.bradykinesia_score}/4{' ':<6} | "
                f"{r.med_status:<10} | "
                f"{r.stress_level:<14} | "
                f"{'Yes' if r.sleep_deprived else 'No'}\n"
            )

    return Response(
        output.getvalue(), mimetype="text/plain",
        headers={"Content-disposition": f"attachment; filename={username}_{current_user_role}_report.txt"}
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)