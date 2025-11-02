# app.py
import os, io, re, base64, requests
import streamlit as st
from PIL import Image
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI
import plotly.graph_objects as go

# ---------------------- Page config ----------------------
st.set_page_config(page_title="Smart Calorie Estimator", page_icon="🍽️", layout="wide")

# ---------------------- Secrets & .env -------------------
# Load .env for local dev; on Streamlit Cloud it uses st.secrets
load_dotenv(find_dotenv(), override=False)

def get_secret(name, default=""):
    return st.secrets.get(name, os.getenv(name, default))

OPENAI_API_KEY   = get_secret("OPENAI_API_KEY")
CLARIFAI_API_KEY = get_secret("CLARIFAI_API_KEY")
APP_PASSWORD     = get_secret("APP_PASSWORD")

client = OpenAI(api_key=OPENAI_API_KEY if OPENAI_API_KEY else None)

# ---------------------- Password Gate --------------------
def check_password():
    """Simple password gate using APP_PASSWORD from secrets/.env."""
    if not APP_PASSWORD:   # no password configured → let pass but warn
        st.warning("⚠️ No password configured. Set APP_PASSWORD in .streamlit/secrets.toml")
        return True
    if st.session_state.get("authed"):
        return True
    st.title("🔒 Protected Access")
    pwd = st.text_input("Password", type="password")
    if st.button("Enter"):
        if pwd == APP_PASSWORD:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()

check_password()

# ---------------------- Helpers --------------------------
@st.cache_data(show_spinner=False, ttl=60*60)
def detect_ingredients(image_bytes: bytes, num_predictions: int = 4):
    """Call Clarifai Food model to detect ingredients from an image."""
    if not CLARIFAI_API_KEY:
        return ["(Clarifai API key missing)"]
    b64_img = base64.b64encode(image_bytes).decode("utf-8")
    headers = {"Authorization": f"Key {CLARIFAI_API_KEY}"}
    payload = {
        "user_app_id": {"user_id": "clarifai", "app_id": "main"},
        "inputs": [{"data": {"image": {"base64": b64_img}}}]
    }
    url = "https://api.clarifai.com/v2/models/food-item-recognition/outputs"
    res = requests.post(url, headers=headers, json=payload, timeout=30)
    res.raise_for_status()
    data = res.json()
    try:
        concepts = data["outputs"][0]["data"]["concepts"]
        return [c["name"] for c in concepts[:num_predictions]]
    except Exception:
        return ["unknown"]

def parse_serving_size(txt: str | None):
    """Parse grams from OpenFoodFacts 'serving_size' strings like '30 g' or '250 ml'."""
    if not txt:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)\s*(g|ml)', txt.lower())
    if m:
        qty = float(m.group(1))
        unit = m.group(2)
        # treat ml ~ g for liquids; good enough for demo
        return qty if unit in ("g", "ml") else None
    return None

@st.cache_data(show_spinner=False, ttl=60*60)
def get_food_info(food_name: str):
    """
    Query OpenFoodFacts for one product and return:
      {
        "kcal_100g": float|None,
        "serving_g": float|None,
        "kcal_serving": float|None,
        "raw_name": str
      }
    """
    try:
        res = requests.get(
            "https://world.openfoodfacts.org/cgi/search.pl",
            params={
                "search_terms": food_name,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 1,
                "fields": "product_name,nutriments,serving_size"
            },
            timeout=20
        )
        res.raise_for_status()
        data = res.json()
        if data.get("products"):
            p = data["products"][0]
            nutr = p.get("nutriments", {})
            kcal_100 = nutr.get("energy-kcal_100g")
            kcal_serv = nutr.get("energy-kcal_serving")
            serving_g = parse_serving_size(p.get("serving_size"))
            return {
                "kcal_100g": kcal_100,
                "serving_g": serving_g,
                "kcal_serving": kcal_serv,
                "raw_name": p.get("product_name") or food_name
            }
    except Exception:
        pass
    return {"kcal_100g": None, "serving_g": None, "kcal_serving": None, "raw_name": food_name}

@st.cache_data(show_spinner=False, ttl=60*60)
def ai_comment_cached(prompt: str, model="gpt-4o-mini", max_tokens=360, temperature=0.3):
    """OpenAI call + auto-continue if the answer seems cut mid-sentence."""
    if not OPENAI_API_KEY:
        return "⚠️ OpenAI API key missing."
    try:
        res = client.chat.completions.create(
            model=model,
            messages=[{"role":"user","content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        text = (res.choices[0].message.content or "").strip()

        if len(text) > 120 and text[-1] not in ".!?":
            res2 = client.chat.completions.create(
                model=model,
                messages=[
                    {"role":"user","content": prompt},
                    {"role":"assistant","content": text},
                    {"role":"user","content":"Continue concisely."}
                ],
                max_tokens=220,
                temperature=temperature
            )
            text += "\n" + (res2.choices[0].message.content or "").strip()
        return text
    except Exception as e:
        return f"[AI error] {e}"

def bmr_mifflin_stjeor(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    """
    Mifflin–St Jeor BMR formula.
    Sex constants: Male = +5, Female = −161, 'Prefer not to say' ≈ −78 (neutral average).
    """
    sex_const = 5 if sex == "Male" else (-161 if sex == "Female" else -78)
    return 10*weight_kg + 6.25*height_cm - 5*age + sex_const

def activity_factor(level: str) -> float:
    """Rough activity factors commonly used in nutrition."""
    return 1.2 if level == "Sedentary" else (1.55 if level == "Moderate" else 1.75)

def tdee_components(bmr: float, level: str):
    """
    Decompose TDEE ≈ BMR + TEF (~10% of TDEE) + NEAT + EAT.
    The split between NEAT/EAT depends on activity level.
    """
    factor = activity_factor(level)
    tdee = bmr * factor
    tef = 0.10 * tdee
    rem = max(0.0, tdee - (bmr + tef))
    if level == "Sedentary":
        eat_share, neat_share = 0.10, 0.90
    elif level == "Moderate":
        eat_share, neat_share = 0.35, 0.65
    else:
        eat_share, neat_share = 0.50, 0.50
    eat = rem * eat_share
    neat = rem * neat_share
    return {"BMR": bmr, "TEF": tef, "NEAT": neat, "EAT": eat, "TDEE": tdee}

# ---------------------- UI -------------------------------
st.title("🍽️ Smart Calorie Estimator")

tab1, tab2 = st.tabs(["👤 User Profile", "🍽️ Meal Analysis"])

# ---------------------- TAB 1 : Profile ------------------
with tab1:
    st.header("👤 User Profile")

    # Sliders for height/weight
    height = st.slider("Height (cm)", 140, 210, 175, step=1)
    weight = st.slider("Weight (kg)", 40, 140, 70, step=1)

    st.write("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏃 Activity level")
        st.markdown(
            "- **Sedentary**: little to no exercise  \n"
            "- **Moderate**: 3–4 workouts / week  \n"
            "- **Active**: intense training or physical job"
        )
        activity = st.selectbox("Activity level", ["Sedentary", "Moderate", "Active"])

    with col2:
        st.subheader("⚧ Sex")
        sex = st.radio("Select", ["Male", "Female", "Prefer not to say"], horizontal=True)

    st.subheader("⚠️ Allergies / Intolerances")
    allergies = st.multiselect(
        "Select your allergies (if any)",
        ["Peanuts", "Tree nuts", "Milk / lactose", "Gluten", "Eggs", "Seafood", "Soy"]
    )

    st.write("---")
    objective = st.text_area(
        "🎯 Personal goal",
        placeholder="e.g., lean bulk, fat loss, maintenance, better health...",
        height=90
    )

    # For demo: fixed age. Add a slider if you want.
    age = 25
    bmr = bmr_mifflin_stjeor(weight, height, age, sex)
    comps = tdee_components(bmr, activity)

    st.subheader("📊 TDEE components (interactive)")
    # Stacked bar with clickable legend
    fig = go.Figure()
    fig.add_trace(go.Bar(name="BMR (Basal Metabolic Rate)", x=["Daily expenditure"], y=[comps["BMR"]], marker_color="#1f77b4"))
    fig.add_trace(go.Bar(name="TEF (Digestion)",             x=["Daily expenditure"], y=[comps["TEF"]], marker_color="#ff7f0e"))
    fig.add_trace(go.Bar(name="NEAT (Non-exercise activity)",x=["Daily expenditure"], y=[comps["NEAT"]], marker_color="#2ca02c"))
    fig.add_trace(go.Bar(name="EAT (Exercise)",              x=["Daily expenditure"], y=[comps["EAT"]], marker_color="#d62728"))
    fig.update_layout(
        barmode="stack",
        height=280, width=640,
        margin=dict(l=20, r=20, t=10, b=10),
        yaxis_title="kcal / day",
        template="plotly_white",
        legend_title="Components (clickable)"
    )
    st.plotly_chart(fig, use_container_width=False, config={"displayModeBar": False})
    st.caption(f"**Estimated TDEE** ≈ **{int(comps['TDEE'])} kcal/day**  •  **BMR** ≈ {int(comps['BMR'])} kcal/day")

    with st.expander("ℹ️ BMR & TDEE — quick explainer"):
        st.markdown(
            "- **BMR (Basal Metabolic Rate)**: minimal energy required to keep the body running at rest (organs, breathing, etc.). Computed here with **Mifflin–St Jeor**.\n"
            "- **TDEE (Total Daily Energy Expenditure)**: total energy burned per day = **BMR** + **TEF** (digestion, ~10%) + **NEAT** (daily movement) + **EAT** (exercise). "
            "NEAT/EAT split depends on your activity level. Values are **practical estimates**."
        )

    st.subheader("🧠 AI profile summary")
    if st.button("Generate AI summary", key="profile_ai"):
        allergies_txt = ", ".join(allergies) if allergies else "none"
        prompt = (
            f"User profile: {height} cm, {weight} kg, age {age}, activity {activity}, sex {sex}, "
            f"allergies {allergies_txt}, goal: {objective or 'not specified'}. "
            "Write a clear 3-sentence summary of nutrition needs with a practical tone."
        )
        with st.spinner("Analyzing profile..."):
            st.info(ai_comment_cached(prompt))

# ---------------------- TAB 2 : Meal ---------------------
with tab2:
    st.header("🍽️ Meal Analysis")

    uploaded = st.file_uploader("📸 Upload a photo", type=["jpg", "jpeg", "png"])

    if uploaded:
        img = Image.open(uploaded).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        image_bytes = buf.getvalue()

        # Columns: compact image on the left
        cimg, cmain = st.columns([1, 2])
        with cimg:
            st.image(img, caption="Preview", width=320)

        with cmain:
            st.markdown("### Step 1 – Ingredient detection")
            show_more = st.checkbox("Show more predictions", value=False)
            num_preds = 20 if show_more else 4

            with st.spinner("Visual analysis..."):
                ingredients = detect_ingredients(image_bytes, num_predictions=num_preds)

            st.write(", ".join(ingredients))

            selected = st.multiselect(
                "Select the correct ingredient(s):",
                ingredients,
                default=ingredients[:1] if ingredients else []
            )

            manual = st.text_input("Add manually (comma-separated)")
            if manual.strip():
                selected.extend([x.strip() for x in manual.split(",") if x.strip()])

            if not selected:
                st.warning("Please add at least one ingredient.")
                st.stop()

            st.markdown("### Step 2 – Calorie estimation")

            weight_mode = st.radio(
                "Weight method",
                ["Uniform", "Serving sizes (OpenFoodFacts)", "Percentages (%)"],
                horizontal=True
            )

            # Pre-fetch OFF nutrition
            food_infos = {ing: get_food_info(ing) for ing in selected}
            weights = {ing: None for ing in selected}

            if weight_mode == "Uniform":
                default_w = st.number_input("Weight per ingredient (g)", 5, 2000, 150, step=5)
                with st.expander("Adjust per ingredient (optional)"):
                    for ing in selected:
                        weights[ing] = st.number_input(
                            f"{ing.capitalize()} (g)", 5, 2000, default_w, step=5, key=f"w_uni_{ing}"
                        )
                for ing in selected:
                    if weights[ing] is None:
                        weights[ing] = default_w

            elif weight_mode == "Serving sizes (OpenFoodFacts)":
                st.caption("Use package serving size when available (otherwise default 150 g).")
                for ing in selected:
                    info = food_infos[ing]
                    suggested = int(info["serving_g"]) if info["serving_g"] else 150
                    label_portion = f"• OFF serving: {int(info['serving_g'])} g" if info["serving_g"] else "• OFF serving: —"
                    weights[ing] = st.number_input(
                        f"{ing.capitalize()} (g) {label_portion}",
                        5, 2000, suggested, step=5, key=f"w_off_{ing}"
                    )

            else:  # Percentages
                total_plate = st.number_input("Total plate weight (g)", 50, 3000, 500, step=10)
                st.caption("Split by percentage (auto-normalized).")
                pct = {}
                cols = st.columns(min(3, len(selected))) if len(selected) >= 3 else st.columns(len(selected))
                sum_raw = 0
                for i, ing in enumerate(selected):
                    with cols[i % len(cols)]:
                        pct[ing] = st.slider(f"{ing.capitalize()} (%)", 0, 100, 100 // len(selected), key=f"pct_{ing}")
                        sum_raw += pct[ing]
                if sum_raw == 0:
                    sum_raw = 1
                for ing in selected:
                    norm = pct[ing] / sum_raw
                    weights[ing] = int(round(total_plate * norm))

            # Calculation
            total_kcal = 0.0
            st.write("**Calories by ingredient:**")
            for ing in selected:
                info = food_infos[ing]
                kcal_100 = info["kcal_100g"]
                kcal_serv = info["kcal_serving"]
                serving_g = info["serving_g"]
                w = float(weights[ing])

                kcal = None
                # If kcal/serving exists and weight ≈ serving, use it
                if kcal_serv and serving_g and 0.85 <= (w / serving_g) <= 1.15:
                    kcal = float(kcal_serv)
                elif kcal_100:
                    kcal = float(kcal_100) * (w / 100.0)

                if kcal is not None:
                    st.write(f"• {ing.capitalize()} ({int(w)} g) ≈ {int(kcal)} kcal")
                    total_kcal += kcal
                else:
                    st.write(f"• {ing.capitalize()} ({int(w)} g) — calorie data unavailable")

            st.success(f"**Estimated total: {int(total_kcal)} kcal**")

            st.markdown("---")
            st.subheader("🧠 AI comment (allergies, goal, simple alternative)")
            if st.button("Analyze meal", key="meal_ai"):
                allergies_txt = ", ".join(allergies) if allergies else "none"
                prompt = (
                    f"Profile: goal = {objective or 'not specified'}, allergies = {allergies_txt}. "
                    f"Meal: {', '.join(selected)} for {int(total_kcal)} kcal. "
                    "Check compatibility with allergies and goal. "
                    "If needed, propose 1 simple alternative. Keep it concise."
                )
                with st.spinner("Analyzing meal..."):
                    st.info(ai_comment_cached(prompt))
    else:
        st.info("📤 Upload a photo to start the analysis.")
