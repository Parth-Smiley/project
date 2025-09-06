import joblib
import difflib

# ✅ Load the pre-trained model (model.pkl must be in the same folder)
model = joblib.load("model.pkl")

# ✅ Full list of symptoms (from Training.csv)
all_symptoms = joblib.load("symptoms_list.pkl")

# ✅ Helper function to correct spelling
def correct_symptom(symptom, all_symptoms):
    matches = difflib.get_close_matches(symptom, all_symptoms, n=1, cutoff=0.6)
    return matches[0] if matches else symptom

# ✅ Take user input in plain text
user_input = input("Enter your symptoms separated by commas (e.g., fever, cough): ")
symptom_list_raw = [sym.strip().lower() for sym in user_input.split(',')]

# ✅ Auto-correct symptoms
symptom_list = [correct_symptom(sym, all_symptoms) for sym in symptom_list_raw]

print("\nCorrected Symptoms:", ", ".join(symptom_list))

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
