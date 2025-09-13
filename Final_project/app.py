from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
import joblib
import difflib
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.secret_key = "super_secret_key"  # Change in production

# Database setup
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///medconnect.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# SocketIO setup
socketio = SocketIO(app, cors_allowed_origins="*")

# -------------------- MODELS --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # "patient" or "doctor"
    specialty = db.Column(db.String(50))  # only for doctors

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient = db.Column(db.String(50), nullable=False)
    doctor = db.Column(db.String(50), nullable=False)
    text = db.Column(db.Text, nullable=False)
    sender = db.Column(db.String(10), nullable=False)  # "patient" or "doctor"


# -------------------- ML MODELS --------------------
model = joblib.load("model.pkl")
all_features = joblib.load("features_list.pkl")
doctor_map = joblib.load("doctor_map.pkl")
model_accuracy = joblib.load("model_accuracy.pkl")
specialties = joblib.load("specialties.pkl")
encoders = joblib.load("encoders.pkl")

symptom_features = [
    f for f in all_features if f not in [
        "Age", "Gender", "Weather", "Last_Meal",
        "Water_Source", "Occupation", "Smoker",
        "Chronic_Disease_History"
    ]
]

questions = [
    ("Age", "What is your age?"),
    ("Gender", "What is your gender? (Male/Female)"),
    ("Weather", "What is the current weather? (Hot/Rainy/Cold/Humid)"),
    ("Last_Meal", "What was your last meal? (Street Food/Home Cooked/Restaurant/Unknown)"),
    ("Water_Source", "What is your main water source? (Tap/Hand Pump/River/Stored Tank)"),
    ("Occupation", "What is your occupation? (Farmer/Student/Worker/Homemaker/Other)"),
    ("Smoker", "Do you smoke? (Yes/No)"),
    ("Chronic_Disease_History", "Do you have chronic disease history? (Yes/No)"),
    ("Symptoms", "Please list your symptoms separated by commas (e.g., fever, cough, stomach pain)")
]

# -------------------- HELPERS --------------------
def correct_symptom(symptom, all_symptoms):
    matches = difflib.get_close_matches(symptom, all_symptoms, n=1, cutoff=0.6)
    return matches[0] if matches else symptom

def correct_input(user_value, valid_options):
    user_value = user_value.strip().lower()
    options = [opt.lower() for opt in valid_options]
    matches = difflib.get_close_matches(user_value, options, n=1, cutoff=0.6)
    if matches:
        idx = options.index(matches[0])
        return valid_options[idx]
    return user_value


# -------------------- ROUTES --------------------
@app.route("/")
def home():
    return render_template("home.html")


# -------- Signup --------
@app.route("/signup-patient", methods=["GET", "POST"])
def signup_patient():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            return render_template("signup.html", role="patient", error="Passwords do not match!")

        if User.query.filter_by(username=username).first():
            return render_template("signup.html", role="patient", error="Username already exists!")

        new_user = User(username=username, password=password, role="patient")
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login_patient"))

    return render_template("signup.html", role="patient")


@app.route("/signup_doctor", methods=["GET", "POST"])
def signup_doctor():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        specialty = request.form.get("specialty")

        if not specialty:
            return render_template("signup.html", role="doctor", specialties=specialties,
                                   error="Please select your specialty")

        if password != confirm_password:
            return render_template("signup.html", role="doctor", specialties=specialties,
                                   error="Passwords do not match!")

        if User.query.filter_by(username=username).first():
            return render_template("signup.html", role="doctor", specialties=specialties,
                                   error="Username already exists!")

        new_user = User(username=username, password=password, role="doctor", specialty=specialty)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login_doctor"))

    return render_template("signup.html", role="doctor", specialties=specialties)


# -------- Login --------
@app.route("/login-patient", methods=["GET", "POST"])
def login_patient():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username, password=password, role="patient").first()
        if user:
            session["patient_username"] = username
            session["role"] = "patient"
            return redirect(url_for("frontend"))

        return render_template("login.html", role="patient", error="Invalid credentials")

    return render_template("login.html", role="patient")


@app.route("/login-doctor", methods=["GET", "POST"])
def login_doctor():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username, password=password, role="doctor").first()
        if user:
            session["doctor_username"] = username
            session["role"] = "doctor"
            return redirect(url_for("doctor_dashboard"))

        return render_template("login.html", role="doctor", error="Invalid credentials")

    return render_template("login.html", role="doctor")


@app.route("/frontend")
def frontend():
    if "patient_username" not in session:
        return redirect(url_for("login_patient"))
    return render_template("Frontend.html", username=session["patient_username"])


@app.route("/logout")
def logout():
    session.pop("patient_username", None)
    session.pop("doctor_username", None)
    session.pop("role", None)
    return redirect(url_for("home"))


# -------- Doctor Dashboard --------
@app.route("/doctor-dashboard", methods=["GET", "POST"])
def doctor_dashboard():
    if "doctor_username" not in session:
        return redirect(url_for("login_doctor"))

    doctor_name = session["doctor_username"]
    selected_patient = request.args.get("patient")  # active patient

    # Handle message sending
    if request.method == "POST" and selected_patient:
        text = request.form["message"]
        new_msg = Message(patient=selected_patient, doctor=doctor_name, text=text, sender="doctor")
        db.session.add(new_msg)
        db.session.commit()

        socketio.emit("new_message", {
            "sender": "doctor",
            "patient": selected_patient,
            "doctor": doctor_name,
            "text": text
        })

        return redirect(url_for("doctor_dashboard", patient=selected_patient))

    # All patients who ever messaged this doctor (for sidebar)
    patient_usernames = db.session.query(Message.patient).filter_by(doctor=doctor_name).distinct().all()
    patients = [p[0] for p in patient_usernames]

    # Messages only with selected patient
    messages = []
    if selected_patient:
        messages = Message.query.filter_by(doctor=doctor_name, patient=selected_patient).all()

    return render_template("doctor_dashboard.html",
                           username=doctor_name,
                           patients=patients,
                           active_patient=selected_patient,
                           messages=messages)


# -------- Chat (Patient) --------
@app.route("/chat", methods=["GET", "POST"])
def chat():
    if "patient_username" not in session:
        return redirect(url_for("login_patient"))

    username = session["patient_username"]
    selected_doctor = request.args.get("doctor")  # active doctor

    # Handle message sending
    if request.method == "POST" and selected_doctor:
        message = request.form["message"]
        new_msg = Message(patient=username, doctor=selected_doctor, text=message, sender="patient")
        db.session.add(new_msg)
        db.session.commit()

        socketio.emit("new_message", {
            "sender": "patient",
            "patient": username,
            "doctor": selected_doctor,
            "text": message
        })

        return redirect(url_for("chat", doctor=selected_doctor))

    # All doctors (for sidebar)
    doctors = {u.username: {"specialty": u.specialty} for u in User.query.filter_by(role="doctor").all()}

    # Messages only with selected doctor
    messages = []
    if selected_doctor:
        messages = Message.query.filter_by(patient=username, doctor=selected_doctor).all()

    return render_template("chat.html",
                           username=username,
                           doctors=doctors,
                           active_doctor=selected_doctor,
                           messages=messages)



@app.route("/clear-chat", methods=["POST"])
def clear_chat():
    if "patient_username" not in session:
        return redirect(url_for("login_patient"))

    username = session["patient_username"]
    doctor = request.form["doctor"]

    Message.query.filter_by(patient=username, doctor=doctor).delete()
    db.session.commit()

    return redirect(url_for("chat"))


# -------- Prediction --------
@app.route("/predict-page")
def predict_page():
    if "patient_username" not in session:
        return redirect(url_for("login_patient"))
    return render_template("index.html", username=session["patient_username"])


@app.route("/predict", methods=["GET", "POST"])
def predict():
    if "answers" not in session:
        session["answers"] = {}
        session["q_index"] = 0

    if request.method == "POST":
        user_answer = request.form["answer"].strip()
        current_feature, _ = questions[session["q_index"]]

        if current_feature == "Gender":
            session["answers"][current_feature] = correct_input(user_answer, ["Male", "Female"])
        elif current_feature == "Weather":
            session["answers"][current_feature] = correct_input(user_answer, ["Hot", "Rainy", "Cold", "Humid"])
        elif current_feature == "Last_Meal":
            session["answers"][current_feature] = correct_input(user_answer, ["Street Food", "Home Cooked", "Restaurant", "Unknown"])
        elif current_feature == "Water_Source":
            session["answers"][current_feature] = correct_input(user_answer, ["Tap", "Hand Pump", "River", "Stored Tank"])
        elif current_feature == "Occupation":
            session["answers"][current_feature] = correct_input(user_answer, ["Farmer", "Student", "Worker", "Homemaker", "Other"])
        elif current_feature in ["Smoker", "Chronic_Disease_History"]:
            session["answers"][current_feature] = correct_input(user_answer, ["Yes", "No"])
        else:
            session["answers"][current_feature] = user_answer

        session["q_index"] += 1

        if session["q_index"] >= len(questions):
            features = {f: 0 for f in all_features}

            for feature in encoders.keys():
                if feature in session["answers"]:
                    val = session["answers"][feature]
                    try:
                        features[feature] = encoders[feature].transform([val])[0]
                    except:
                        features[feature] = 0

            features["Age"] = int(session["answers"]["Age"])

            raw = [s.strip().lower() for s in session["answers"]["Symptoms"].split(",")]
            corrected = [correct_symptom(s, symptom_features) for s in raw]
            for s in corrected:
                if s in features:
                    features[s] = 1

            input_vector = [features[f] for f in all_features]
            proba = model.predict_proba([input_vector])[0]
            diseases = model.classes_
            results = sorted(zip(proba, diseases), reverse=True)[:3]

            output = []
            for prob, disease in results:
                output.append({
                    "disease": disease,
                    "probability": round(prob * 100, 2),
                    "doctor": doctor_map.get(disease, "General Physician")
                })

            session.pop("answers", None)
            session.pop("q_index", None)

            return jsonify({"results": output, "accuracy": round(model_accuracy * 100, 2)})

    _, question_text = questions[session["q_index"]]
    return jsonify({"question": question_text})





# -------------------- MAIN --------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)
