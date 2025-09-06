from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import joblib
from flask import flash
import os
import json

app = Flask(__name__)
app.secret_key = "super_secret_key"  # Change for security

# Load model & symptoms list
model = joblib.load("model.pkl")
all_symptoms = joblib.load("symptoms_list.pkl")
doctor_map = joblib.load("doctor_map.pkl")

# Path to user storage
users_file = "users.json"

# Ensure users.json exists
if not os.path.exists(users_file):
    with open(users_file, 'w') as f:
        json.dump({}, f)

def load_users():
    with open(users_file, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(users_file, 'w') as f:
        json.dump(users, f)

# ✅ Homepage
@app.route('/')
def home():
    return render_template('home.html')

@app.route("/signup-patient", methods=["GET", "POST"])
def signup_patient():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with open("users.json") as f:
            users = json.load(f)

        users[username] = {"password": password, "role": "patient"}

        with open("users.json", "w") as f:
            json.dump(users, f, indent=2)

        return redirect(url_for("login_patient"))

    return render_template("signup.html")


@app.route("/signup-doctor", methods=["GET", "POST"])
def signup_doctor():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with open("users.json") as f:
            users = json.load(f)

        users[username] = {"password": password, "role": "doctor"}

        with open("users.json", "w") as f:
            json.dump(users, f, indent=2)

        return redirect(url_for("login_doctor"))

    return render_template("signup.html")

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

    return render_template("doctor_dashboard.html", username=session['username'], messages=doctor_msgs)
# ✅ Prediction page (requires login)


@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'logged_in' not in session or session['role'] != 'patient':
        return redirect(url_for('login'))

    users = load_users()
    doctors = {u: d for u, d in users.items() if d["role"] == "doctor"}

    with open("messages.json", "r") as f:
        messages = json.load(f)

    if request.method == 'POST':
        doctor = request.form['doctor']
        text = request.form['message']

        messages.append({
            "patient": session['username'],
            "doctor": doctor,
            "text": text,
            "sender": "patient"
        })

        with open("messages.json", "w") as f:
            json.dump(messages, f, indent=2)

        return redirect(url_for('chat'))

    return render_template("chat.html", doctors=doctors, username=session['username'], messages=messages)

@app.route('/clear-chat', methods=['POST'])
def clear_chat():
    if 'logged_in' not in session or session['role'] != 'patient':
        return redirect(url_for('login'))

    doctor = request.form.get('doctor')
    if not doctor:
        return redirect(url_for('chat'))

    # Load and filter out this patient's messages with that doctor
    with open("messages.json", "r") as f:
        messages = json.load(f)

    messages = [
        m for m in messages
        if not (m.get("patient") == session['username'] and m.get("doctor") == doctor)
    ]

    with open("messages.json", "w") as f:
        json.dump(messages, f, indent=2)

    return redirect(url_for('chat'))


@app.route('/predict-page')
def predict_page():
    if 'logged_in' in session:
        return render_template('index.html', username=session['username'])
    return redirect(url_for('login'))

# ✅ Prediction API
@app.route('/predict', methods=['POST'])
def predict():
    if 'logged_in' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    raw_text = request.form['symptoms']
    user_symptoms = [sym.strip().lower() for sym in raw_text.split(',')]
    
    # Convert to binary vector
    input_vector = [1 if symptom in user_symptoms else 0 for symptom in all_symptoms]

    # Predict probabilities
    proba = model.predict_proba([input_vector])[0]
    diseases = model.classes_

    # Sort top 3 predictions
    sorted_probs = sorted(zip(proba, diseases), reverse=True)[:3]
    results = []
    for prob, disease in sorted_probs:
        doctor = doctor_map.get(disease, "General Physician")
        results.append({
            "disease": disease,
            "probability": round(prob * 100, 2),
            "doctor": doctor
        })

    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True)
