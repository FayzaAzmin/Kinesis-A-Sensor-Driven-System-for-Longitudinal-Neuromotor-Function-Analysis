import csv
import io
import os
import re
from flask import send_file, session, flash, redirect, url_for
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
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
        flash("Invalid Credentials. Please try again.", "danger")
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

        # Extracts raw hidden inputs and maps completely empty strings directly to None
        raw_phone = request.form.get('full_mobile_number')
        mobile_number = raw_phone.strip() if (raw_phone and raw_phone.strip()) else None

        if User.query.filter_by(username=username).first():
            flash("Username already registered.", "danger")
            return redirect(url_for('signup'))

        if mobile_number and User.query.filter_by(mobile_number=mobile_number).first():
            flash("Contact number already registered.", "danger")
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
        flash("Profile picture successfully removed.", "info")
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
    flash("Physiological Factors status updated.", "success")
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

    accel_magnitudes = [(f['Accel_X'] ** 2 + f['Accel_Y'] ** 2 + f['Accel_Z'] ** 2) ** 0.5 for f in sensor_data]
    avg_magnitude = sum(accel_magnitudes) / len(accel_magnitudes)

    calculated_tremor_score = min(4, int(avg_magnitude * 2))

    speed_deltas = [abs(accel_magnitudes[i] - accel_magnitudes[i - 1]) for i in range(1, len(accel_magnitudes))]
    avg_velocity_delta = sum(speed_deltas) / len(speed_deltas) if speed_deltas else 0

    if calculated_tremor_score > 1:
        calculated_brady_score = 0
    else:
        if avg_velocity_delta < 0.15:
            calculated_brady_score = 4
        elif avg_velocity_delta < 0.35:
            calculated_brady_score = 3
        elif avg_velocity_delta < 0.65:
            calculated_brady_score = 2
        elif avg_velocity_delta < 1.10:
            calculated_brady_score = 1
        else:
            calculated_brady_score = 0

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

    if session.get("role") != 'patient':
        return jsonify({"status": "error", "message": "Real-time stream interface restricted to patients"}), 403

    latest_records = Telemetry.query.filter_by(patient_username=session["username"]).order_by(
        Telemetry.timestamp.desc()).limit(15).all()
    latest_records.reverse()

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
                flash("Incorrect Patient Identification.", "danger")
                current_pid = ""

    records = []
    status_text = "HEALTH STATUS VERIFICATION PENDING"
    suggestion_text = "No sensor telemetry records received."

    if target_patient:
        records = Telemetry.query.filter_by(patient_username=target_patient).order_by(Telemetry.timestamp.asc()).all()

        if records:
            avg_tremor = sum(r.resting_tremor_score for r in records) / len(records)
            avg_brady = sum(r.bradykinesia_score for r in records) / len(records)

            if avg_tremor > 1.0 or avg_brady > 1.0:
                status_text = "UNHEALTHY CONDITIONS OBSERVED"
                suggestion_text = "Anomalous motor fluctuations detected. It is highly recommended to consult a certified health professional for a checkup."
            else:
                status_text = "HEALTHY SYSTEM STATUS APPROVED"
                suggestion_text = "Calculated scores are stable."

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
    records = Telemetry.query.filter_by(patient_username=username).all()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=40
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'],
        fontName='Helvetica-Bold', fontSize=20, leading=24,
        textColor=colors.HexColor('#1A365D'), spaceAfter=6
    )
    meta_style = ParagraphStyle(
        'MetaText', parent=styles['Normal'],
        fontName='Helvetica', fontSize=10, leading=14,
        textColor=colors.HexColor('#718096'), spaceAfter=15
    )
    header_cell_style = ParagraphStyle(
        'HeaderCell', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, leading=12,
        textColor=colors.white
    )
    body_cell_style = ParagraphStyle(
        'BodyCell', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, leading=12,
        textColor=colors.HexColor('#2D3748')
    )
    story = []

    story.append(Paragraph(f"KINESIS CLINICAL METRIC REPORT: {username.upper()}", title_style))
    gen_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    story.append(Paragraph(f"Generated on: {gen_time} | Access Authorization: {current_user_role.upper()}", meta_style))
    story.append(Spacer(1, 10))

    if not records:
        story.append(
            Paragraph("No operational system telemetry data streams recorded for this profile yet.", body_cell_style))

    elif current_user_role == 'clinician':
        table_data = [[
            Paragraph("TIMESTAMP (UTC)", header_cell_style),
            Paragraph("MED STATE", header_cell_style),
            Paragraph("STRESS LEVEL", header_cell_style),
            Paragraph("SLEEP DEPRIVED", header_cell_style),
            Paragraph("TREMOR (0-4)", header_cell_style),
            Paragraph("TAP SCORE", header_cell_style),
            Paragraph("FREQ (Hz)", header_cell_style),
            Paragraph("AMP (RMS)", header_cell_style),
            Paragraph("ENTROPY", header_cell_style)
        ]]

        for r in records:
            ts_str = r.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            table_data.append([
                Paragraph(ts_str, body_cell_style),
                Paragraph(str(r.med_status), body_cell_style),  # 1. MED STATE (ON/OFF)
                Paragraph(str(r.stress_level), body_cell_style),  # 2. STRESS LEVEL
                Paragraph("Yes" if r.sleep_deprived else "No", body_cell_style),  # 3. SLEEP DEPRIVED (Yes/No)
                Paragraph(str(r.resting_tremor_score), body_cell_style),  # 4. TREMOR (0-4)
                Paragraph(str(r.bradykinesia_score), body_cell_style),  # 5. TAP SCORE
                Paragraph(f"{r.dominant_frequency_hz:.2f}", body_cell_style),  # 6. FREQ (Hz)
                Paragraph(f"{r.signal_amplitude_rms:.4f}", body_cell_style),  # 7. AMP (RMS)
                Paragraph(f"{r.spectral_entropy:.3f}", body_cell_style)  # 8. ENTROPY
            ])

        log_table = Table(table_data, colWidths=[95, 60, 60, 60, 60, 60, 60, 60, 65])

    else:
        table_data = [[
            Paragraph("RECORD TIME", header_cell_style),
            Paragraph("TREMOR", header_cell_style),
            Paragraph("TAP SPEED", header_cell_style),
            Paragraph("MED STATE", header_cell_style),
            Paragraph("STRESS LEVEL", header_cell_style),
            Paragraph("SLEEP DEPRIVED", header_cell_style)
        ]]

        for r in records:
            ts_str = r.timestamp.strftime('%Y-%m-%d %H:%M')
            table_data.append([
                Paragraph(ts_str, body_cell_style),
                Paragraph(f"{r.resting_tremor_score}/4", body_cell_style),
                Paragraph(f"{r.bradykinesia_score}/4", body_cell_style),
                Paragraph(str(r.med_status), body_cell_style),
                Paragraph(str(r.stress_level), body_cell_style),
                Paragraph("Yes" if r.sleep_deprived else "No", body_cell_style)
            ])

        log_table = Table(table_data, colWidths=[132, 70, 80, 80, 100, 90])

    if records:
        log_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2B6CB0')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7FAFC')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ]))
        story.append(log_table)

    doc.build(story)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{username}_{current_user_role}_report.pdf",
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)