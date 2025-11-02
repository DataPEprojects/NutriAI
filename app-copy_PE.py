# app.py
import os, io, re, base64, requests
import streamlit as st
from PIL import Image
from dotenv import load_dotenv, find_dotenv
from openai import OpenAI
import plotly.graph_objects as go

# ---------------------- Config page ----------------------
st.set_page_config(page_title="Smart Calorie Estimator", page_icon="🍽️", layout="wide")

# ---------------------- Secrets & .env -------------------
# Charge .env (utile en dev local) — sur Cloud c'est st.secrets
load_dotenv(find_dotenv(), override=False)

def get_secret(name, default=""):
    return st.secrets.get(name, os.getenv(name, default))

OPENAI_API_KEY   = get_secret("OPENAI_API_KEY")
CLARIFAI_API_KEY = get_secret("CLARIFAI_API_KEY")
APP_PASSWORD     = get_secret("APP_PASSWORD")

client = OpenAI(api_key=OPENAI_API_KEY if OPENAI_API_KEY else None)

# ---------------------- Password Gate --------------------
def check_password():
    if not APP_PASSWORD:   # si pas de mdp configuré : on laisse passer mais on informe
        st.warning("⚠️ Aucun mot de passe configuré. Ajoute APP_PASSWORD dans .streamlit/secrets.toml")
        return True
    if st.session_state.get("authed"):
        return True
    st.title("🔒 Accès protégé")
    pwd = st.text_input("Mot de passe", type="password")
    if st.button("Entrer"):
        if pwd == APP_PASSWORD:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Mauvais mot de passe.")
    st.stop()

check_password()

# ---------------------- Helpers --------------------------
@st.cache_data(show_spinner=False, ttl=60*60)
def detect_ingredients(image_bytes: bytes, num_predictions: int = 4):
    """Appel Clarifai pour détecter les ingrédients."""
    if not CLARIFAI_API_KEY:
        return ["(clé Clarifai manquante)"]
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
    """Extrait les grammes depuis 'serving_size' OpenFoodFacts (ex: '30 g', '250 ml')."""
    if not txt:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)\s*(g|ml)', txt.lower())
    if m:
        qty = float(m.group(1))
        unit = m.group(2)
        return qty if unit in ("g", "ml") else None
    return None

@st.cache_data(show_spinner=False, ttl=60*60)
def get_food_info(food_name: str):
    """
    Retourne:
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
    """OpenAI + auto-continue si la réponse est tronquée."""
    if not OPENAI_API_KEY:
        return "⚠️ Clé OpenAI manquante."
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
                    {"role":"user","content":"Continue en restant concis."}
                ],
                max_tokens=220,
                temperature=temperature
            )
            text += "\n" + (res2.choices[0].message.content or "").strip()
        return text
    except Exception as e:
        return f"[Erreur IA] {e}"

def bmr_mifflin_stjeor(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    """Mifflin-St Jeor; constantes sexe: Homme=+5, Femme=-161, 'Préférer ne pas dire'≈ -78."""
    sex_const = 5 if sex == "Homme" else (-161 if sex == "Femme" else -78)
    return 10*weight_kg + 6.25*height_cm - 5*age + sex_const

def activity_factor(level: str) -> float:
    return 1.2 if level == "Sédentaire" else (1.55 if level == "Modéré" else 1.75)

def tdee_components(bmr: float, level: str):
    """Décompose TDEE ≈ BMR + TEF (~10% TDEE) + NEAT + EAT (répartition selon activité)."""
    factor = activity_factor(level)
    tdee = bmr * factor
    tef = 0.10 * tdee
    rem = max(0.0, tdee - (bmr + tef))
    if level == "Sédentaire":
        eat_share, neat_share = 0.10, 0.90
    elif level == "Modéré":
        eat_share, neat_share = 0.35, 0.65
    else:
        eat_share, neat_share = 0.50, 0.50
    eat = rem * eat_share
    neat = rem * neat_share
    return {"BMR": bmr, "TEF": tef, "NEAT": neat, "EAT": eat, "TDEE": tdee}

# ---------------------- UI -------------------------------
st.title("🍽️ Smart Calorie Estimator")

tab1, tab2 = st.tabs(["👤 Profil utilisateur", "🍽️ Analyse du repas"])

# ---------------------- TAB 1 : Profil -------------------
with tab1:
    st.header("👤 Profil utilisateur")

    # Sliders taille/poids
    taille = st.slider("Taille (cm)", 140, 210, 175, step=1)
    poids  = st.slider("Poids (kg)", 40, 140, 70, step=1)

    st.write("---")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏃 Niveau d'activité")
        st.markdown(
            "- **Sédentaire** : peu d'exercice  \n"
            "- **Modéré** : 3-4 séances/semaine  \n"
            "- **Actif** : entraînement intense ou travail physique"
        )
        activite = st.selectbox("Niveau d'activité", ["Sédentaire", "Modéré", "Actif"])

    with col2:
        st.subheader("⚧ Sexe")
        sexe = st.radio("Sélection", ["Homme", "Femme", "Préférer ne pas dire"], horizontal=True)

    st.subheader("⚠️ Allergies / Intolérances")
    allergies = st.multiselect(
        "Sélectionne tes allergies (si applicable)",
        ["Arachides", "Fruits à coque", "Lait / lactose", "Gluten", "Œufs", "Fruits de mer", "Soja"]
    )

    st.write("---")
    objectif = st.text_area(
        "🎯 Objectif personnel",
        placeholder="Ex: prise de masse, perte de poids, maintien, meilleure santé...",
        height=90
    )

    # Hypothèse d'âge 25 (ajoute un slider si besoin)
    age = 25
    bmr = bmr_mifflin_stjeor(poids, taille, age, sexe)
    comps = tdee_components(bmr, activite)

    st.subheader("📊 TDEE par composantes (interactif)")
    # Stacked bar avec légende cliquable
    fig = go.Figure()
    fig.add_trace(go.Bar(name="BMR (Métabolisme basal)", x=["Dépense journalière"], y=[comps["BMR"]], marker_color="#1f77b4"))
    fig.add_trace(go.Bar(name="TEF (Digestion)",             x=["Dépense journalière"], y=[comps["TEF"]], marker_color="#ff7f0e"))
    fig.add_trace(go.Bar(name="NEAT (Mouvements du quotidien)", x=["Dépense journalière"], y=[comps["NEAT"]], marker_color="#2ca02c"))
    fig.add_trace(go.Bar(name="EAT (Sport/Exercice)",        x=["Dépense journalière"], y=[comps["EAT"]], marker_color="#d62728"))
    fig.update_layout(
        barmode="stack",
        height=280, width=640,
        margin=dict(l=20, r=20, t=10, b=10),
        yaxis_title="kcal / jour",
        template="plotly_white",
        legend_title="Composantes (cliquables)"
    )
    st.plotly_chart(fig, use_container_width=False, config={"displayModeBar": False})
    st.caption(f"**TDEE** estimé ≈ **{int(comps['TDEE'])} kcal/j**  •  **BMR** ≈ {int(comps['BMR'])} kcal/j")

    with st.expander("ℹ️ BMR & TDEE — explications"):
        st.markdown(
            "- **BMR (Basal Metabolic Rate)** : énergie minimale pour faire fonctionner l’organisme au repos (respiration, organes, etc.). Calculé ici via **Mifflin–St Jeor**.\n"
            "- **TDEE (Total Daily Energy Expenditure)** : dépense totale par jour = **BMR** + **TEF** (digestion, ~10%) + **NEAT** (mouvements du quotidien) + **EAT** (sport). "
            "Les parts NEAT/EAT varient selon ton niveau d’activité. Les valeurs sont des **estimations** pratiques."
        )

    st.subheader("🧠 Résumé IA du profil")
    if st.button("Générer résumé IA", key="profile_ai"):
        prompt = (
            f"Profil utilisateur : {taille} cm, {poids} kg, âge {age} ans, activité {activite}, sexe {sexe}, "
            f"allergies {', '.join(allergies) if allergies else 'aucune'}, objectif : {objectif}. "
            "Fais un résumé clair en 3 phrases de ses besoins nutritionnels et garde un ton pratique."
        )
        with st.spinner("Analyse du profil..."):
            st.info(ai_comment_cached(prompt))

# ---------------------- TAB 2 : Repas --------------------
with tab2:
    st.header("🍽️ Analyse du repas")

    uploaded = st.file_uploader("📸 Upload une photo", type=["jpg", "jpeg", "png"])

    if uploaded:
        img = Image.open(uploaded).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        image_bytes = buf.getvalue()

        # Colonnes : image compacte à gauche
        cimg, cmain = st.columns([1, 2])
        with cimg:
            st.image(img, caption="Aperçu", width=320)

        with cmain:
            st.markdown("### Étape 1 – Détection des ingrédients")
            show_more = st.checkbox("Afficher plus de prédictions", value=False)
            num_preds = 20 if show_more else 4

            with st.spinner("Analyse visuelle..."):
                ingredients = detect_ingredients(image_bytes, num_predictions=num_preds)

            st.write(", ".join(ingredients))

            selected = st.multiselect(
                "Sélectionne les ingrédients corrects :",
                ingredients,
                default=ingredients[:1] if ingredients else []
            )

            manual = st.text_input("Ajouter manuellement (séparés par des virgules)")
            if manual.strip():
                selected.extend([x.strip() for x in manual.split(",") if x.strip()])

            if not selected:
                st.warning("Ajoute au moins un ingrédient.")
                st.stop()

            st.markdown("### Étape 2 – Estimation des calories")

            weight_mode = st.radio(
                "Méthode de poids",
                ["Uniforme", "Portions (OpenFoodFacts)", "Proportions (%)"],
                horizontal=True
            )

            # Pré-fetch OFF
            food_infos = {ing: get_food_info(ing) for ing in selected}
            weights = {ing: None for ing in selected}

            if weight_mode == "Uniforme":
                default_w = st.number_input("Poids par ingrédient (g)", 5, 2000, 150, step=5)
                with st.expander("Ajuster individuellement (optionnel)"):
                    for ing in selected:
                        weights[ing] = st.number_input(
                            f"{ing.capitalize()} (g)", 5, 2000, default_w, step=5, key=f"w_uni_{ing}"
                        )
                for ing in selected:
                    if weights[ing] is None:
                        weights[ing] = default_w

            elif weight_mode == "Portions (OpenFoodFacts)":
                st.caption("Utilise la portion de l’emballage si disponible (sinon 150 g par défaut).")
                for ing in selected:
                    info = food_infos[ing]
                    suggested = int(info["serving_g"]) if info["serving_g"] else 150
                    label_portion = f"• portion OFF: {int(info['serving_g'])} g" if info["serving_g"] else "• portion OFF: —"
                    weights[ing] = st.number_input(
                        f"{ing.capitalize()} (g) {label_portion}",
                        5, 2000, suggested, step=5, key=f"w_off_{ing}"
                    )

            else:  # Proportions
                total_plate = st.number_input("Poids total de l’assiette (g)", 50, 3000, 500, step=10)
                st.caption("Répartis en pourcentage (normalisation automatique).")
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

            # Calcul
            total_kcal = 0.0
            st.write("**Détail des calories :**")
            for ing in selected:
                info = food_infos[ing]
                kcal_100 = info["kcal_100g"]
                kcal_serv = info["kcal_serving"]
                serving_g = info["serving_g"]
                w = float(weights[ing])

                kcal = None
                if kcal_serv and serving_g and 0.85 <= (w / serving_g) <= 1.15:
                    kcal = float(kcal_serv)
                elif kcal_100:
                    kcal = float(kcal_100) * (w / 100.0)

                if kcal is not None:
                    st.write(f"• {ing.capitalize()} ({int(w)} g) ≈ {int(kcal)} kcal")
                    total_kcal += kcal
                else:
                    st.write(f"• {ing.capitalize()} ({int(w)} g) — données caloriques indisponibles")

            st.success(f"**Total estimé : {int(total_kcal)} kcal**")

            st.markdown("---")
            st.subheader("🧠 Commentaire IA (allergies, objectif, alternative)")
            if st.button("Analyser le repas", key="meal_ai"):
                allergies_txt = ", ".join(allergies) if allergies else "aucune"
                prompt = (
                    f"Profil : objectif = {objectif or 'non précisé'}, allergies = {allergies_txt}. "
                    f"Repas : {', '.join(selected)} pour {int(total_kcal)} kcal. "
                    "Analyse la compatibilité avec les allergies et l'objectif. "
                    "Propose 1 alternative simple si nécessaire. Reste concis."
                )
                with st.spinner("Analyse du repas..."):
                    st.info(ai_comment_cached(prompt))
    else:
        st.info("📤 Upload une photo pour commencer l’analyse.")
