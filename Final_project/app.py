from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import joblib
from flask import flash
import os
import json
import difflib

app = Flask(__name__)
app.secret_key = "super_secret_key"  # Change for security

# Load model & symptoms list
model = joblib.load("model.pkl")
all_features = joblib.load("features_list.pkl")
doctor_map = joblib.load("doctor_map.pkl")
model_accuracy = joblib.load("model_accuracy.pkl")
specialties = joblib.load("specialties.pkl")
encoders = joblib.load("encoders.pkl")

USERS_FILE = "users.json"
MESSAGES_FILE = "messages.json"


def load_users():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            json.dump({}, f)   # empty dict for users
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def load_messages():
    if not os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, "w") as f:
            json.dump([], f)   # empty list for messages
    with open(MESSAGES_FILE, "r") as f:
        return json.load(f)

def save_messages(messages):
    with open(MESSAGES_FILE, "w") as f:
        json.dump(messages, f, indent=2)

# Symptoms subset
symptom_features = [f for f in all_features if f not in ["Age", "Gender", "Weather", "Last_Meal", "Water_Source", "Occupation", "Smoker", "Chronic_Disease_History"]]

# Chatbot questions order
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




def correct_symptom(symptom, all_symptoms):
    matches = difflib.get_close_matches(symptom, all_symptoms, n=1, cutoff=0.6)
    return matches[0] if matches else symptom

# Helper to correct categorical input
def correct_input(user_value, valid_options):
    user_value = user_value.strip().lower()
    options = [opt.lower() for opt in valid_options]
    matches = difflib.get_close_matches(user_value, options, n=1, cutoff=0.6)
    if matches:
        # return original case version
        idx = options.index(matches[0])
        return valid_options[idx]
    return user_value  # fallback



# ✅ Homepage
@app.route('/')
def home():
    return render_template('home.html')

@app.route("/signup-patient", methods=["GET", "POST"])
def signup_patient():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        # ✅ Password match check
        if password != confirm_password:
            return render_template("signup.html", role="patient", error="Passwords do not match!")

        users = load_users()
        if username in users:
            return render_template("signup.html", role="patient", error="Username already exists!")

        users[username] = {"password": password, "role": "patient"}
        save_users(users)

        return redirect(url_for("login_patient"))

    return render_template("signup.html", role="patient")


@app.route("/signup_doctor", methods=["GET", "POST"])
def signup_doctor():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        specialty = request.form.get("specialty")  # ✅ safer than ["specialty"]
        if not specialty:
            return render_template("signup.html", role="doctor", specialties=specialties,
                           error="Please select your specialty")

        # ✅ Password match check
        if password != confirm_password:
            return render_template("signup.html", role="doctor", error="Passwords do not match!", specialties=specialties)

        users = load_users()
        if username in users:
            return render_template("signup.html", role="doctor", error="Username already exists!", specialties=specialties)

        # Save doctor with specialty
        users[username] = {"password": password, "role": "doctor", "specialty": specialty}
        save_users(users)

        if not specialty:
            return render_template("signup.html", role="doctor", specialties=specialties,
                           error="Please select your specialty")

        return redirect(url_for("login_doctor"))

    return render_template("signup.html", role="doctor", specialties=specialties)


# ✅ Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        users = load_users()

        if username in users and users[username]["password"] == password and users[username]["role"] == role:
            session['logged_in'] = True
            session['username'] = username
            session['role'] = role

            if role == "doctor":
                return redirect(url_for('doctor_dashboard'))
            else:
                return redirect(url_for('frontend'))
        else:
            return render_template('login.html', error="Invalid credentials or role mismatch")

    # For GET request → just show login form
    return render_template('login.html')

@app.route("/login-patient", methods=["GET", "POST"])
def login_patient():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with open("users.json") as f:
            users = json.load(f)

        if username in users and users[username]["password"] == password:
            session["username"] = username
            session["role"] = "patient"
            return redirect(url_for("frontend"))

        return redirect(url_for("login_patient"))

    return render_template("login.html", role="patient")


@app.route("/login-doctor", methods=["GET", "POST"])
def login_doctor():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with open("users.json") as f:
            users = json.load(f)

        if username in users and users[username]["password"] == password:
            session["username"] = username
            session["role"] = "doctor"
            return redirect(url_for("doctor_dashboard"))

        return redirect(url_for("login_doctor"))

    return render_template("login.html", role="doctor")

@app.route("/frontend")
def frontend():
    # optionally protect with session check
    if "username" not in session:
        return redirect(url_for("login_patient"))
    return render_template("Frontend.html", username=session["username"])

# ✅ Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/doctor-dashboard', methods=['GET', 'POST'])
def doctor_dashboard():
    if "username" not in session:
        return redirect(url_for("login_doctor"))

    with open("messages.json", "r") as f:
        messages = json.load(f)

    # Show only messages for this doctor
    doctor_msgs = [m for m in messages if m['doctor'] == session['username']]

    # 🔹 Load doctor specialty from users.json
    with open("users.json", "r") as f:
        users = json.load(f)
    specialty = users[session['username']].get("specialty", "Not specified")

    if request.method == 'POST':
        patient = request.form['patient']
        text = request.form['message']

        messages.append({
            "patient": patient,
            "doctor": session['username'],
            "text": text,
            "sender": "doctor"
        })

        with open("messages.json", "w") as f:
            json.dump(messages, f, indent=2)

        return redirect(url_for('doctor_dashboard'))

    return render_template(
        "doctor_dashboard.html",
        username=session['username'],
        specialty=specialty,   # ✅ pass specialty to template
        messages=doctor_msgs
    )

# ✅ Prediction page (requires login)


@app.route("/chat", methods=["GET", "POST"])
def chat():
    if "username" not in session:
        return redirect(url_for("login_patient"))

    username = session["username"]

    if request.method == "POST":
        doctor = request.form["doctor"]
        message = request.form["message"]

        with open("messages.json", "r") as f:
            messages = json.load(f)

        messages.append({"patient": username, "doctor": doctor, "text": message, "sender": "patient"})

        with open("messages.json", "w") as f:
            json.dump(messages, f, indent=2)

        return redirect(url_for("chat"))

    with open("messages.json", "r") as f:
        messages = json.load(f)

    with open("users.json", "r") as f:
        doctors = {u: d for u, d in json.load(f).items() if d["role"] == "doctor"}

    # 🔹 Build doctor -> specialty mapping
    doctor_specialties = {u: details.get("specialty", "General Physician") for u, details in doctors.items()}

    return render_template("chat.html", username=username, doctors=doctors, doctor_specialties=doctor_specialties, messages=messages)


@app.route("/clear-chat", methods=["POST"])
def clear_chat():
    if "username" not in session:
        return redirect(url_for("login_patient"))

    username = session["username"]
    doctor = request.form["doctor"]

    with open("messages.json", "r") as f:
        messages = json.load(f)

    messages = [m for m in messages if not (m["patient"] == username and m["doctor"] == doctor)]

    with open("messages.json", "w") as f:
        json.dump(messages, f, indent=2)

    return redirect(url_for("chat"))



@app.route("/predict-page")
def predict_page():
    if "username" not in session:
        return redirect(url_for("login_patient"))
    return render_template("index.html", username=session["username"])

# ✅ Prediction API
@app.route("/predict", methods=["GET", "POST"])
def predict():
    if "answers" not in session:
        session["answers"] = {}
        session["q_index"] = 0

    if request.method == "POST":
        user_answer = request.form["answer"].strip()
        current_feature, _ = questions[session["q_index"]]

        # Save the answer
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

        # ✅ If finished → run prediction
        if session["q_index"] >= len(questions):
            features = {f: 0 for f in all_features}

            # Encode categorical values
            for feature in encoders.keys():
                if feature in session["answers"]:
                    val = session["answers"][feature]
                    try:
                        features[feature] = encoders[feature].transform([val])[0]
                    except:
                        features[feature] = 0

            # Age
            features["Age"] = int(session["answers"]["Age"])

            # Symptoms
            raw = [s.strip().lower() for s in session["answers"]["Symptoms"].split(",")]
            corrected = [correct_symptom(s, symptom_features) for s in raw]
            for s in corrected:
                if s in features:
                    features[s] = 1

            # Predict
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

            # Reset chatbot state
            session.pop("answers", None)
            session.pop("q_index", None)

            return jsonify({
                "results": output,
                "accuracy": round(model_accuracy * 100, 2)
            })

    # ✅ Ask next question
    current_feature, question_text = questions[session["q_index"]]
    return jsonify({"question": question_text})


    







if __name__ == '__main__':
    app.run(debug=True)
