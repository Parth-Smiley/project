import joblib
import difflib

# Load model and utils
model = joblib.load("model.pkl")
all_features = joblib.load("features_list.pkl")
encoders = joblib.load("encoders.pkl")
doctor_map = joblib.load("doctor_map.pkl")

# Symptoms subset
symptom_features = [f for f in all_features if f not in ["Age", "Gender", "Weather", "Last_Meal", "Water_Source", "Occupation", "Smoker", "Chronic_Disease_History"]]

# Helper
def correct_symptom(symptom, all_symptoms):
    matches = difflib.get_close_matches(symptom, all_symptoms, n=1, cutoff=0.6)
    return matches[0] if matches else symptom

# Collect inputs
age = int(input("Enter Age: "))
gender = input("Enter Gender (Male/Female): ")
weather = input("Weather (Hot/Rainy/Cold/Humid): ")
last_meal = input("Last Meal (Street Food/Home Cooked/Restaurant/Unknown): ")
water_source = input("Water Source (Tap/Hand Pump/River/Stored Tank): ")
occupation = input("Occupation (Farmer/Student/Worker/Homemaker/Other): ")
smoker = input("Do you smoke? (Yes/No): ")
chronic = input("Chronic Disease History? (Yes/No): ")
symptom_input = input("Enter symptoms separated by commas: ")

# Build features
features = {f: 0 for f in all_features}
features["Age"] = age

for feature, val in [
    ("Gender", gender),
    ("Weather", weather),
    ("Last_Meal", last_meal),
    ("Water_Source", water_source),
    ("Occupation", occupation),
    ("Smoker", smoker),
    ("Chronic_Disease_History", chronic),
]:
    if feature in encoders:
        try:
            features[feature] = encoders[feature].transform([val])[0]
        except:
            features[feature] = 0

symptom_list_raw = [s.strip().lower() for s in symptom_input.split(",")]
symptom_list = [correct_symptom(s, symptom_features) for s in symptom_list_raw]
for s in symptom_list:
    if s in features:
        features[s] = 1

# Predict
input_vector = [features[f] for f in all_features]
proba = model.predict_proba([input_vector])[0]
diseases = model.classes_

# Show top 3
print("\nTop 3 Predictions:")
for prob, disease in sorted(zip(proba, diseases), reverse=True)[:3]:
    print(f"{disease} → {prob*100:.2f}% (Doctor: {doctor_map.get(disease, 'General Physician')})")
