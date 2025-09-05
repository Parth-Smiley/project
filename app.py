from flask import Flask, render_template, request, jsonify
import joblib
import os

app = Flask(__name__)

# Load model
model_path = os.path.join(os.path.dirname(__file__), "model.pkl")
model = joblib.load(model_path)

# Load symptoms list
symptoms_path = os.path.join(os.path.dirname(__file__), "symptoms_list.pkl")
all_symptoms = joblib.load(symptoms_path)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    raw_text = request.form['symptoms']
    user_symptoms = [sym.strip().lower() for sym in raw_text.split(',')]
    
    # Convert to binary vector
    input_vector = [1 if symptom in user_symptoms else 0 for symptom in all_symptoms]

    # Get prediction probabilities
    proba = model.predict_proba([input_vector])[0]
    diseases = model.classes_

    # Sort and get top 3
    sorted_probs = sorted(zip(proba, diseases), reverse=True)[:3]
    results = [{"disease": disease, "probability": round(prob*100, 2)} for prob, disease in sorted_probs]

    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True)
