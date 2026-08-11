# Ziwena — Phase 1 (CLI)

This folder contains a minimal Phase 1 implementation: a terminal chat loop that loads your Phase 0 personality and sends messages to a model.

Files added:
- `ziwena_phase1.py` — the CLI chat program. Reads `ziwena-phase0-mehdi.md` for the system prompt.
- `requirements.txt` — suggested packages to install.
- `.env.example` — example environment variables.

Quick start
1. Copy `.env.example` to `.env` and set `ZIWENA_GEMINI_API_KEY` (or `OPENAI_API_KEY`).
2. (Optional) set `ZIWENA_MODEL` to your preferred model name.
3. Create a virtualenv and install deps:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

4. Run the CLI:

```bash
python ziwena_phase1.py
```

5. Run the Streamlit app:

```bash
streamlit run streamlit_app.py
```

The Streamlit UI shows a full agent page with chat, command support, controls, and memory state. It is the recommended path for a polished local deployment.

Notes & security
- If you accidentally pasted a real API key into chat or a public place, rotate it (delete the old key and create a new one) before running the code.
- The CLI tries `google-generativeai` first, then falls back to `openai` if installed. If neither is installed the script runs in dry-run mode and prints the prompt it would send.

Next steps
- Tweak the system prompt in `ziwena-phase0-mehdi.md` until the personality feels right.
- Phase 2 will add persistent memory (RAG) using a local vector DB.
