import streamlit as st
from PIL import Image
import random
from transformers import pipeline
import requests, base64, io

API_KEY = "0b4269ed23cd4c73b18d918411f79b41"
USER_ID = "clarifai"     # always 'clarifai' for public models
APP_ID = "main"          # 'main' is Clarifai’s public app
MODEL_ID = "food-item-recognition"

def detect_ingredients(image, num_predictions=4):
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
        return [c["name"] for c in concepts[:num_predictions]]
    except Exception as e:
        print("Clarifai API error:", e)
        print("Full response:", res.text)
        return ["unknown"]

def get_calories(food_name):
    try:
        res = requests.get(
            f"https://world.openfoodfacts.org/cgi/search.pl",
            params={"search_terms": food_name, "search_simple": 1, "action": "process", "json": 1, "page_size": 1}
        )
        data = res.json()
        if data["products"]:
            nutr = data["products"][0].get("nutriments", {})
            return nutr.get("energy-kcal_100g", None)
    except Exception as e:
        print("OpenFoodFacts error:", e)
    return None

st.set_page_config(page_title="AI Calorie Estimator", page_icon="🍽️")
st.title("🍽️ Smart Calorie Estimator (Local Demo)")

uploaded = st.file_uploader("Upload a food image", type=["jpg", "jpeg", "png"])

if uploaded:
    img = Image.open(uploaded)
    st.image(img, caption="Uploaded image", use_column_width=True)

    st.markdown("### Step 1 – Detecting ingredients…")
    show_more = st.checkbox("Show more predictions")
    num_preds = None
    if show_more:
        # show all predictions from Clarifai
        # But we don't know total count, so get all concepts
        # We'll call detect_ingredients with a large number to get all
        # But Clarifai might limit, so let's request 20 max
        num_preds = 20
    else:
        num_preds = 4
    ingredients = detect_ingredients(img, num_predictions=num_preds)
    st.write(", ".join(ingredients))

    selected = st.multiselect(
        "Select the correct ingredient(s):",
        ingredients,
        default=ingredients[:1]  # pre-select the top guess
    )

    if not selected:
        st.warning("Please select at least one ingredient.")
        st.stop()

    manual_input = st.text_input("Manually add ingredients (comma-separated)")
    if manual_input.strip():
        manual_ings = [ing.strip() for ing in manual_input.split(",") if ing.strip()]
        selected.extend(manual_ings)

    st.markdown("### Step 2 – Estimating calories")

    adjust_weights = st.checkbox("Adjust weights per ingredient")
    weights = {}
    if adjust_weights:
        st.write("Set the weight (grams) for each ingredient:")
        for ing in selected:
            weights[ing] = st.slider(
                f"{ing.capitalize()} weight (grams)",
                10, 1000, 150, key=f"weight_{ing}"
            )
    else:
        for ing in selected:
            weights[ing] = 150  # default weight if not adjusting

    total = 0
    st.write("**Ingredient Calories:**")
    for ing in selected:
        kcal_per_100g = get_calories(ing)
        weight = weights.get(ing, 150)
        if kcal_per_100g is not None:
            kcal = kcal_per_100g * (weight / 100)
            st.write(f"• **{ing.capitalize()}** ({weight}g) ≈ {int(kcal)} kcal")
            total += kcal
        else:
            st.write(f"• **{ing.capitalize()}** ({weight}g) ≈ calorie info not found")

    st.markdown("---")
    st.success(f"**Total Estimated Calories: {int(total)} kcal**")
else:
    st.info("👆 Upload a food picture to start")
