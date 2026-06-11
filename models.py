from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import string

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'patient', 'caregiver', 'clinician'

    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    mobile_number = db.Column(db.String(20), nullable=True)
    profile_pic = db.Column(db.String(150), nullable=False, default='default.png')
    unique_patient_id = db.Column(db.String(12), unique=True, nullable=True)

    @staticmethod
    def generate_patient_id():
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))


class Telemetry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_username = db.Column(db.String(50), db.ForeignKey('user.username'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    resting_tremor_score = db.Column(db.Integer, nullable=False, default=0)
    bradykinesia_score = db.Column(db.Integer, nullable=False, default=0)

    med_status = db.Column(db.String(10), nullable=False, default="OFF")
    sleep_deprived = db.Column(db.Boolean, nullable=False, default=False)
    stress_level = db.Column(db.String(20), nullable=False, default="Normal")

    dominant_frequency_hz = db.Column(db.Float, nullable=False, default=0.0)
    signal_amplitude_rms = db.Column(db.Float, nullable=False, default=0.0)
    spectral_entropy = db.Column(db.Float, nullable=False, default=0.0)