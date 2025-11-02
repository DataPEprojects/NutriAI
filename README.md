
NutriAI — Smart Calorie Estimator (TXT README)
==============================================

NutriAI is a small Streamlit web app that estimates a meal’s calories from a photo
and gives a short, personalized nutrition comment.

- Upload a food photo → the app detects ingredients (Clarifai)
- It fetches nutrition per 100 g / per serving (OpenFoodFacts)
- You choose weights (uniform / per serving / % of plate) → calorie estimate
- AI comment: checks allergies & goal and proposes a simple alternative (OpenAI)
- Optional password gate for demos/classes


0) What are APIs? (Simple explanation)
--------------------------------------
Think of APIs as waiters that fetch data/services for us on demand.

- Clarifai API: we send a PHOTO → it returns PROBABLE INGREDIENTS (e.g., “french fries”, “hamburger”).
- OpenFoodFacts API: we send an INGREDIENT NAME → it returns kcal per 100 g and often kcal per serving.
- OpenAI API: we send a SHORT TEXT (goal, allergies, meal summary) → it returns a short comment in human language.

We don’t store your personal data. We only send small requests needed to make the app work.


1) Demo Flow
------------
[You] --upload photo--> [Streamlit UI]
     \
      \--> Clarifai (image → ingredients)
           ↓
        OpenFoodFacts (nutrition per 100 g / per serving)
           ↓
      You choose weights (uniform / serving / %)
           ↓
        → Total kcal
           ↓
      OpenAI (short comment: allergies/goal/alternative)
           ↓
      Result ready for class/demo ✨


2) Quick Start (Local)
----------------------
Requirements: Python 3.10+ is recommended. Windows, macOS, Linux supported.

(1) Clone or download the repo and open a terminal inside the project folder.

(2) (Optional) Create and activate a virtual environment:

    # Windows (PowerShell)
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1

    # macOS / Linux
    python -m venv .venv
    source .venv/bin/activate

(3) Install dependencies:

    pip install -r requirements.txt

(4) Add secrets (NEVER commit secrets to GitHub):
    - Create folder: .streamlit
    - Create file:   .streamlit/secrets.toml
    - Put your keys (QUOTES REQUIRED):

      OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
      CLARIFAI_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxx"
      APP_PASSWORD = "demo1234"

(5) Run the app (choose the file name you use):

    streamlit run app-copy_PE.py
    # or
    # streamlit run app.py

(6) Open the browser link printed by Streamlit.
    If asked, enter the password (the value of APP_PASSWORD).

Note: .gitignore already prevents committing .env and .streamlit/secrets.toml.


3) Deploy on Streamlit Cloud
----------------------------
(1) Push this repo to your own GitHub (without any secrets).

(2) Go to: https://share.streamlit.io → “New app”

(3) Select your repo, branch (e.g., main), and entry file (app-copy_PE.py or app.py).

(4) In App → Settings → Secrets, paste:

    OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
    CLARIFAI_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxx"
    APP_PASSWORD = "choose-a-strong-password"

(5) Save, then Reboot the app. Share link + password.


4) How to Use
-------------
TAB 1 — "Profil utilisateur"
- Set Height (cm) and Weight (kg).
- Choose Activity: Sedentary / Moderate / Active.
- Choose Sex: Male / Female / Prefer not to say (affects BMR formula).
- Select Allergies (multi-select): peanuts, lactose, gluten, etc.
- Write Objective: bulk, cut, maintain, better health, etc.

You will see:
- BMR (Basal Metabolic Rate): energy to keep your body alive at rest (organs, breathing).
- TDEE (Total Daily Energy Expenditure): your daily burn = BMR + TEF + NEAT + EAT.
  * TEF: Thermic Effect of Food (digestion), approx. 10% of TDEE.
  * NEAT: Non-Exercise Activity Thermogenesis (walking, chores).
  * EAT: Exercise Activity Thermogenesis (sports/training).
- An interactive Plotly chart shows these colored components.
  You can click on legend items to hide/show them.

Press “Générer résumé IA” for a short profile summary using OpenAI.

TAB 2 — "Analyse du repas"
1) Upload a photo of your meal.
2) The app detects ingredients (you can correct the list or add new ones).
3) Choose weight mode (no hardcoding):
   - Uniforme: one gram value for all ingredients (you can override per ingredient).
   - Portions (OpenFoodFacts): uses serving size from the OFF product if available.
   - Proportions (%): set total plate weight and split by percentages (auto-normalized).
4) The app fetches kcal per 100 g or per serving (used when your weight ≈ serving).
5) You get a per-ingredient kcal estimate, a total, and a short AI comment that:
   - checks allergies vs meal
   - checks goal vs meal
   - suggests a simple alternative if needed

The numbers are estimates for learning/demo, not medical advice.


5) What’s Inside the Code (overview)
------------------------------------
Main file: app-copy_PE.py (or app.py if you renamed it).

Key functions:
- detect_ingredients(image_bytes, num_predictions):
    Calls Clarifai. Returns a list like ["french fries", "hamburger", "lettuce"].

- get_food_info(food_name):
    Calls OpenFoodFacts for one product. Returns a dict:
      {
        "kcal_100g": float | None,
        "serving_g": float | None,      # parsed from strings like "30 g" or "250 ml"
        "kcal_serving": float | None,
        "raw_name": str
      }

- ai_comment_cached(prompt):
    Calls OpenAI to generate a short comment.
    If the text seems cut mid-sentence, the function automatically asks to “Continue concisely”
    and appends that continuation.

- bmr_mifflin_stjeor(weight_kg, height_cm, age, sex):
    Mifflin–St Jeor BMR formula. Sex constants:
      Male +5, Female −161, Neutral −78.

- tdee_components(bmr, activity_level):
    Splits TDEE into BMR + TEF (~10%) + NEAT + EAT based on the chosen activity level.

Password gate:
- The app reads APP_PASSWORD from secrets.
- If set, users must enter it before using the app. Great for classroom demos.


6) BMR & TDEE (short explanation)
---------------------------------
BMR (Basal Metabolic Rate): minimal energy your body needs to run essential functions at rest.

TDEE (Total Daily Energy Expenditure): the total energy you burn in a day.
TDEE ≈ BMR + TEF + NEAT + EAT
 - TEF (Thermic Effect of Food): energy spent digesting food (~10% of TDEE).
 - NEAT: daily movement not considered exercise (walking to the bus, typing, chores).
 - EAT: planned exercise or sports (gym, running, swimming).

In the app, the Plotly bar chart stacks these components with different colors.
You can click a legend item (e.g., NEAT) to hide or show that component.


7) Privacy & Security (plain English)
-------------------------------------
- Keys live in .streamlit/secrets.toml locally, or in Streamlit Cloud Secrets.
  Never hardcode keys in the Python file; never push secrets to GitHub.
- Requests are minimal:
  - Clarifai: image bytes for detection
  - OpenFoodFacts: ingredient names
  - OpenAI: a short text like “Goal: lean bulk, Allergies: eggs, Meal: burger + fries ~700 kcal”
- We do not write these data to a database.
- Costs for a small classroom demo are generally low, but always check provider pricing.


8) Troubleshooting
------------------
- StreamlitSecretNotFoundError: Invalid date or number
  → Your .streamlit/secrets.toml is malformed.
    All values must be quoted, no stray characters at the top.
    Example:
      OPENAI_API_KEY = "sk-xxxx"
      CLARIFAI_API_KEY = "xxxx"
      APP_PASSWORD = "demo1234"

- Clarifai 401 / Unauthorized
  → Wrong key or wrong header; fix key in secrets.toml.

- Ingredient not found / calories missing
  → OpenFoodFacts might not have that specific item. Try a more generic keyword.

- OpenAI response cut mid-sentence
  → The helper function already auto-continues. Click again if needed.

- Module not found
  → Install dependencies: pip install -r requirements.txt (inside your venv).


9) Repo Structure (minimal)
---------------------------
.
├── app-copy_PE.py         # main app (entry file)
├── requirements.txt       # Python dependencies
├── .gitignore             # prevents pushing secrets & env files
└── .streamlit/
    └── secrets.toml       # local only (never commit)

On Streamlit Cloud, you will paste secrets in the app’s Secrets UI.


10) License / Intended Use
--------------------------
This project is for personal/educational demonstration. If you plan to use it commercially,
review the API providers’ terms (Clarifai, OpenFoodFacts, OpenAI) and add a proper license
file that fits your use case.


11) Using ChatGPT to help coding (transparency note)
----------------------------------------------------
We used ChatGPT as a coding assistant to:
- sketch UI components quickly (Streamlit)
- propose clean handling for API responses & errors
- write this README and simplify wording for non-technical users

The app itself does not “run” ChatGPT locally; it only calls the OpenAI API to generate short text.
You can disable that feature by not setting an OpenAI key or removing the related button.
