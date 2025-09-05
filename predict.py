import joblib

# ✅ Load the pre-trained model (model.pkl must be in the same folder)
model = joblib.load("model.pkl")

# ✅ Full list of symptoms (from Training.csv)
all_symptoms = joblib.load("symptoms_list.pkl")

# ✅ Take user input in plain text
user_input = input("Enter your symptoms separated by commas (e.g., fever, cough): ")
symptom_list = [sym.strip().lower() for sym in user_input.split(',')]

# ✅ Convert symptoms to binary input vector
input_vector = [1 if symptom in symptom_list else 0 for symptom in all_symptoms]

# ✅ Predict probabilities
proba = model.predict_proba([input_vector])[0]
diseases = model.classes_

# ✅ Sort and get top 3 predictions
sorted_probs = sorted(zip(proba, diseases), reverse=True)[:3]

# ✅ Show results
print("\nTop 3 Possible Diseases:")
for prob, disease in sorted_probs:
    print(f"{disease}: {prob*100:.2f}%")
