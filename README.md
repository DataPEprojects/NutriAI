# 🍽️ NutriAI — AI-First Meal Estimation (Technical Notes for Reviewers)

Please access the app through the following link:<br>
https://nutriai-ai64vt6ahikabfkdjrbpjk.streamlit.app/
The password is demo1234
---

## 1) Executive Summary

NutriAI is an **AI‑first pipeline** that:
1. takes a **photo** of a meal,
2. uses **computer vision** to propose likely **ingredients**,  
3. queries an **open nutrition knowledge base** for **calorie facts**,  
4. lets the user **ground** the results (weights/servings), and
5. asks a **language model** for a **short, actionable comment** that checks allergies and goals.

This design shows **multiple AI modalities** working together: **perception (CV)**, **retrieval** from an open dataset, and **language reasoning** for user-facing guidance—while keeping human-in-the-loop control on the critical step (weights/composition).

---

## 2) What’s “AI” here? (Multi‑model stack)

- **Vision model (Clarifai, public food model)**  
  Given an image, returns a **ranked list of food concepts** (ingredients).  
  *Why it matters:* showcases image understanding beyond simple labels, acts as the entry point for retrieval.

- **Open nutrition retrieval (OpenFoodFacts)**  
  For each ingredient name, fetches **kcal/100 g** and, when present, **serving size** and **kcal/serving**.  
  *Why it matters:* replaces hardcoded tables with a public **knowledge source**, testing robustness to variability.

- **Language model (OpenAI)**  
  Given a compact, **grounded summary** (allergies, goal, ingredients, energy estimate), produces a **concise comment** with a proposed **simple alternative** when relevant.  
  *Why it matters:* demonstrates **reasoning & personalization** constrained by the app’s structured context (reduces hallucination).

---

## 3) System Design (High Level)

**Flow**
```
Image → Vision (Clarifai) → Top-k ingredients
                 ↓
           OpenFoodFacts lookup (kcal/100g, serving_g, kcal/serving)
                 ↓
        Human-in-the-loop weight selection
                 ↓
         Calorie math (per-ingredient, total)
                 ↓
  LLM summary (allergies/goal check + 1 simple alternative)
```

**Key design choices**
- **User correction first:** ingredient list is **editable** before any calculation (prevents CV errors from propagating).
- **Three weight modes:**  
  1) Uniform grams, 2) Serving sizes (OFF), 3) Percentages of a total plate weight.  
  This turns a fuzzy vision problem into a **controllable estimation** workflow.
- **Grounded prompting:** the LLM only sees **structured facts** (goal, allergies, list of ingredients, kcal). No raw image; no uncontrolled external browsing.
- **Caching & latency:** repeated lookups are cached; CV and OFF calls are bounded by timeouts to keep the UI responsive.

---

## 4) Core Components (Low-to-Mid Level)

### 4.1 Ingredient Detection (CV)
- API: Clarifai food-item-recognition (public app/model)
- Output: list of `{name, confidence}`; we keep **top‑k** names (k configurable).  
- Guardrails:
  - Timeout & error handling → fallback to `["unknown"]` rather than crashing.
  - The UI **shows all predictions**; the user can **remove/rename** entries and **add** missing ones.

### 4.2 Nutrition Retrieval (OpenFoodFacts)
- Endpoint: `search.pl` with `product_name`, `nutriments`, `serving_size`
- Parsed fields:
  - `energy-kcal_100g`
  - `serving_size` → parsed to grams when possible (e.g., `"30 g"`, `"250 ml"`)
  - `energy-kcal_serving` (if available)
- Heuristic: if a chosen weight `w` is **≈ serving** (within **±15%**), use **kcal/serving**; otherwise use **kcal/100 g** × `w/100`.
- Benefits: handles branded items that include realistic serving sizes; remains usable when only 100 g data exists.

### 4.3 Weighting Modes (Human‑in‑the‑Loop)
1. **Uniform**: set one gram value for all ingredients; optional per‑ingredient override.
2. **Serving sizes (OFF)**: prefill each ingredient with its **serving_g** when known; user can adjust.
3. **Percentages (%)**: user sets a **total plate weight** and assigns **percentages** per ingredient; the app normalizes them to grams.

### 4.4 Calorie Math
For each ingredient *i* with chosen weight `w_i`:
- if OFF provides both `serving_g` and `kcal_serving` and `w_i ≈ serving_g`:  
  `kcal_i = kcal_serving`
- else if `kcal_100g` is available:  
  `kcal_i = kcal_100g × (w_i / 100)`
- Total is `Σ kcal_i`. Missing facts are reported clearly (no silent guesses).

### 4.5 Profile Modeling (BMR/TDEE)
- **BMR** via **Mifflin–St Jeor**; sex constants used in a **transparent** way.
- **TDEE** = BMR + **TEF (~10%)** + **NEAT** + **EAT**; the NEAT/EAT split follows **activity level** (Sedentary/Moderate/Active).
- Visualization: **Plotly** stacked bar with clickable legend to toggle components.

### 4.6 LLM Reasoning (Commentary)
- Model called with **low temperature** and **token limit** to keep answers **focused** and **bounded**.
- Prompt is **fully grounded** (goal, allergies, ingredient list, kcal estimate).  
- If the model stops mid‑sentence, a **single “continue concisely”** follow‑up is automatically issued and appended.
- Output is intentionally **brief** (few sentences) to avoid “nutrition advice cosplay”.

---

## 5) Reliability, UX & Guardrails

- **Editable predictions:** users can correct ingredients and add missing ones.
- **Graceful failures:** timeouts/HTTP errors yield **explicit messages** instead of stack traces.
- **Caching:** repeated requests for the same inputs are cached to minimize API calls.
- **Units parsing:** serving strings like `"30 g"` or `"250 ml"` are normalized when possible.
- **Transparent math:** per‑ingredient details are displayed before the total.
- **Deterministic LLM settings:** conservative temperature and short prompts reduce drift/hallucination.
- **No silent defaults:** when data is missing, the app **says it** (and invites a manual correction).

---

## 6) Privacy & Data Handling

- Images are sent only to the **vision API** for recognition.  
- The **LLM** receives **structured text** (no image, no PII): goal, allergies (if provided), ingredient names, and a numeric kcal estimate.
- No database is used; the app keeps everything **ephemeral** in session state.
- The UI encourages users to **avoid sensitive data**; inputs are used only to produce the on‑screen result.

---

## 7) Known Limitations

- **Vision ambiguity:** mixed dishes or occluded items can be mislabeled (e.g., “lettuce dilemma”). Human confirmation fixes this.
- **OpenFoodFacts coverage:** some items lack serving data; calorie density can vary by recipe/brand.
- **Beverages & density:** `ml→g` is approximate; liquid density varies (water vs oils).  
- **Portion estimation:** without scales, grams remain an estimate; percentages mode helps but still relies on user judgment.
- **LLM scope:** commentary is deliberately short and grounded; it isn’t medical advice and avoids prescriptive coaching.

---

## 8) Suggested Extensions (Next Iterations)

- **Instance segmentation** (per‑region weights) or **depth-based** estimates for volume → grams.
- **Macro breakdown** (protein/carbs/fats) and **fiber** where OFF provides them.
- **Barcode scanning** fallback when images are hard to parse.
- **Strict grounding** mode where the LLM can only choose from templates.
- **Batch mode** for day-level summaries and consistency checks vs. user goals.
- **Lightweight local models** for offline demos (quantized CV + rule‑based comments).

---

## 9) Minimal Run Notes (Local Only)

> These notes are for reviewers who want to validate the pipeline locally.  
> They purposely omit any cloud/deployment specifics.

- **Dependencies:** listed in `requirements.txt` (Streamlit, requests, Pillow, Plotly, python-dotenv, openai).  
- **Environment variables expected:**  
  - `OPENAI_API_KEY` — for the LLM comment (optional if you disable the button)  
  - `CLARIFAI_API_KEY` — for ingredient detection  
- **Entry point:** `app.py`  
- **Start:** `streamlit run app.py`

*(If environment variables are unset, the app will surface clear messages and keep running where possible.)*

---

## 10) Repository Layout (Essentials)

```
.
├── app.py                # Streamlit UI + pipeline orchestration
├── requirements.txt      # Python dependencies
└── README.md             # This document
```

---

## 11) Quick Glance at Key Functions

- `detect_ingredients(image_bytes, k)` → top‑k ingredient names from the CV API.  
- `get_food_info(name)` → OFF lookup & robust parsing of kcal fields and serving sizes.  
- `tdee_components(bmr, level)` → BMR + TEF + NEAT + EAT (activity‑dependent split).  
- `ai_comment_cached(prompt)` → short, grounded output; auto‑continue if truncated.

---

## 12) Conclusion

The project demonstrates an **AI‑centric** application: it chains **vision**, **open knowledge retrieval**, and **language reasoning**, while keeping the human decisively **in‑control** of the uncertain step (portion size). The guardrails (grounded prompts, short outputs, explicit fallbacks, and caching) aim to make the system **trustworthy in a classroom setting** and **easy to audit**.
