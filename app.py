import streamlit as st
from PIL import Image
import random
from transformers import pipeline
import requests, base64, io

API_KEY = "0b4269ed23cd4c73b18d918411f79b41"
USER_ID = "clarifai"     # always 'clarifai' for public models
APP_ID = "main"          # 'main' is Clarifai’s public app
MODEL_ID = "food-item-recognition"

def detect_ingredients(image):
    # Convert image to base64
    buf = io.BytesIO()
    image.save(buf, format="JPEG")
    b64_img = base64.b64encode(buf.getvalue()).decode("utf-8")

    # Send to Clarifai API
    headers = {"Authorization": f"Key {API_KEY}"}
    payload = {
        "user_app_id": {"user_id": USER_ID, "app_id": APP_ID},
        "inputs": [{"data": {"image": {"base64": b64_img}}}]
    }
    res = requests.post(
        f"https://api.clarifai.com/v2/models/{MODEL_ID}/outputs",
        headers=headers,
        json=payload
    )

    # Parse API response
    try:
        concepts = res.json()["outputs"][0]["data"]["concepts"]
        return [c["name"] for c in concepts[:4]]
    except Exception as e:
        print("Clarifai API error:", e)
        print("Full response:", res.text)
        return ["unknown"]

calories_db = {
    "tomato": 18, "cheese": 402, "dough": 265, "lettuce": 15,
    "rice": 130, "chicken": 239, "broccoli": 34,
    "salmon": 208, "egg": 155, "pasta": 131, "beef": 250
}

st.set_page_config(page_title="AI Calorie Estimator", page_icon="🍽️")
st.title("🍽️ Smart Calorie Estimator (Local Demo)")

uploaded = st.file_uploader("Upload a food image", type=["jpg", "jpeg", "png"])

if uploaded:
    img = Image.open(uploaded)
    st.image(img, caption="Uploaded image", use_column_width=True)

    st.markdown("### Step 1 – Detecting ingredients…")
    ingredients = detect_ingredients(img)
    st.write(", ".join(ingredients))

    st.markdown("### Step 2 – Estimating calories")
    portion = st.slider("Select estimated portion size (grams per ingredient)", 50, 300, 150)

    total = 0
    for ing in ingredients:
        kcal = calories_db.get(ing, 100) * portion / 100
        st.write(f"• **{ing.capitalize()}** ≈ {int(kcal)} kcal")
        total += kcal

    st.markdown("---")
    st.success(f"**Total Estimated Calories: {int(total)} kcal**")
else:
    st.info("👆 Upload a food picture to start")
