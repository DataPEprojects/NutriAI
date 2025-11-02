# 🍽️ NutriAI — Smart Calorie Estimator

NutriAI is a lightweight **Streamlit** app that estimates the calories of a meal from a photo 📸  
and generates a short, personalized nutrition comment using **AI** (OpenAI). It also calculates and visualizes **BMR** and **TDEE** with an interactive Plotly chart.

---

## ✨ Features

- **Image → Ingredients** with **Clarifai** (public food model)  
- **Nutrition facts** via **OpenFoodFacts** (kcal per 100 g and per serving when available)  
- **Flexible weights**: *Uniform* grams, *Serving sizes* (from OFF), or *Percentages* of a total plate weight  
- **AI comment** checks **allergies** and **goal** and suggests a **simple alternative**  
- **BMR/TDEE** interactive **Plotly** chart (stacked, clickable legend)  
- Optional **password gate** (classroom/demo friendly)  

---

## 🧭 How it works (flow)

```text
[You] --upload photo--> [Streamlit UI]
          │
          ├─► Clarifai (image → top ingredients)
          │
          ├─► OpenFoodFacts (kcal/100g, serving_g, kcal/serving)
          │
          ├─► You pick weight mode (Uniform | Serving sizes | % of total)
          │
          ├─► Per-ingredient kcal + Total kcal
          │
          └─► OpenAI (short comment: allergies + goal + 1 simple alternative)
```

> This is a **demo/learning** app — values are **estimates**, not medical advice.

---

## 🚀 Quick Start (Local)

> Requirements: **Python 3.10+** (Windows/macOS/Linux).

1) **Clone** the repo and open a terminal in the project folder.

2) *(Optional)* Create & activate a virtual environment:

```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

3) **Install dependencies**:

```bash
pip install -r requirements.txt
```

4) **Add secrets** (⚠️ never commit secrets):

Create the folder **`.streamlit`**, then the file **`.streamlit/secrets.toml`** with **quotes** around values:

```toml
OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
CLARIFAI_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxx"
APP_PASSWORD = "demo1234"  # optional but recommended
```

5) **Run** the app:

```bash
streamlit run app.py
```

6) Open the browser link printed by Streamlit (enter the password if prompted).

> `.gitignore` already prevents pushing `.env` and `.streamlit/secrets.toml`.

---

## ☁️ Deploy on Streamlit Cloud

1. Push your repo to GitHub (no secrets).  
2. Go to **https://share.streamlit.io** → **New app**  
3. Select your repo (e.g., `DataPEprojects/NutriAI`), branch (e.g., `main`), and entry file **`app.py`**  
4. In **Settings → Secrets**, paste:

```toml
OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
CLARIFAI_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxx"
APP_PASSWORD = "choose-a-strong-password"
```

5. Save → **Reboot** the app → share the link + password 🎉

**Short description** (for the Streamlit “App description” box):

> Upload a meal photo, auto-detect ingredients (Clarifai), fetch kcal (OpenFoodFacts), pick weights, and get an instant calorie estimate + short AI comment. Includes interactive BMR/TDEE chart. Password-ready for demos.

---

## 🧪 Usage

### Tab 1 — **User Profile**
- Height (cm), Weight (kg)
- Activity: *Sedentary* / *Moderate* / *Active*
- Sex: *Male* / *Female* / *Prefer not to say*
- Allergies (multi-select)
- Goal (free text)

You’ll get:
- **BMR (Basal Metabolic Rate)** — energy at rest (computed with **Mifflin–St Jeor**)  
- **TDEE (Total Daily Energy Expenditure)** = BMR + **TEF** (~10%, digestion) + **NEAT** (non‑exercise movement) + **EAT** (exercise)  
- **Plotly** stacked bar chart with clickable legend (toggle components)

**AI Summary** button → concise 3‑sentence recap of the profile.

### Tab 2 — **Meal Analysis**
1. Upload a meal photo  
2. App detects ingredients (you can correct/add)  
3. Choose **weight mode**:
   - **Uniform**: one gram value for all (per‑ingredient overrides allowed)
   - **Serving sizes (OpenFoodFacts)**: uses package serving when available
   - **Percentages (%)**: set **total plate weight** and split by % (auto-normalized)
4. App uses **kcal/100 g** or **kcal/serving** (when weight ≈ serving)  
5. Shows **per‑ingredient kcal**, **total kcal**, and a short **AI comment**:
   - Checks **allergies** vs meal
   - Checks **goal** vs meal
   - Suggests **one simple alternative** if needed

---

## 🧠 Code tour (high level)

- `detect_ingredients(image_bytes, n)` → Clarifai food model → `["fries", "burger", "lettuce", …]`  
- `get_food_info(name)` → OpenFoodFacts → `{kcal_100g, serving_g, kcal_serving, raw_name}`  
- `ai_comment_cached(prompt)` → OpenAI (auto‑continue if the model cuts mid‑sentence)  
- `bmr_mifflin_stjeor(w, h, age, sex)` → BMR (Mifflin–St Jeor; sex constants: Male +5, Female −161, Neutral −78)  
- `tdee_components(bmr, activity)` → BMR + TEF (~10% of TDEE) + NEAT + EAT (split varies with activity)  
- **Password gate** via `APP_PASSWORD` (local secrets or Cloud secrets)

---

## 🔒 Privacy & Security

- **Secrets** live in `.streamlit/secrets.toml` (local) or Streamlit Cloud **Secrets** — **never** hardcode or commit keys.  
- Requests are minimal:
  - Clarifai: the image bytes (for detection)
  - OpenFoodFacts: ingredient names
  - OpenAI: a short text summary (goal, allergies, kcal)
- No database writes; this is a demo app.
- Costs for small classroom demos are generally low — always check provider pricing.

---

## 🛠 Troubleshooting

- **StreamlitSecretNotFoundError: Invalid date/number**  
  Your `secrets.toml` is malformed. Put quotes around **every** value and keep the top of file clean:
  ```toml
  OPENAI_API_KEY = "sk-xxxx"
  CLARIFAI_API_KEY = "xxxx"
  APP_PASSWORD = "demo1234"
  ```

- **Clarifai 401 / Unauthorized** → wrong or missing API key.

- **Ingredient kcal missing** → OpenFoodFacts might not have that specific item. Try a more generic term.

- **AI stops mid‑sentence** → handled by `ai_comment_cached` (auto‑continue). Click again if needed.

- **Module not found** → `pip install -r requirements.txt` inside your venv.

---

## 📂 Minimal repo structure

```
.
├── app.py
├── requirements.txt
├── .gitignore
└── .streamlit/
    └── secrets.toml   # local only (never commit)
```

---

## 📄 License

Educational demo. For commercial usage, review provider terms (Clarifai, OpenFoodFacts, OpenAI) and add a suitable license.

---

## 🙌 Credits

Built by **Paul‑Elie** with: **Streamlit**, **Clarifai**, **OpenFoodFacts**, **OpenAI**.
