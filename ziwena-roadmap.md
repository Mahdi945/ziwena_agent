# Ziwena — build roadmap

A personal life agent, built step by step. Each phase is usable on its own — you don't need to finish the whole thing to get value.

## Phase 0 — Define what Ziwena actually is to you

Before writing code, write a short doc (even 1 page) answering:
- What tone should Ziwena have? Direct, gentle, funny, strictly practical?
- What life areas does it help with first? (pick 1–2 to start, not all 5)
- What should it NEVER do without asking you first? (e.g. never message someone on your behalf)
- What counts as "knowing you"? List 10–15 facts about yourself you'd want it to always remember.

This becomes Ziwena's system prompt later. Skipping this step is why most personal-agent projects stall — the code is easy, deciding what you actually want is the real work.

## Phase 1 — Core chat loop (weekend 1)

**Stack:** Python + Gemini free API (or Groq)

1. `pip install google-generativeai python-dotenv`
2. Store your API key in a `.env` file, never in code
3. Write a basic loop: read your message → send to Gemini with a system prompt describing Ziwena's personality → print the reply
4. Test it in the terminal until the personality feels right

**Deliverable:** a command-line Ziwena you can chat with, no memory yet.

## Phase 2 — Give Ziwena memory (weekend 2)

This is the RAG layer from before.

1. Create a folder of text files: `about_me.md`, `goals.md`, `journal/2026-08-11.md`, etc.
2. `pip install chromadb sentence-transformers`
3. Chunk each file into paragraphs, embed them, store in ChromaDB (runs locally, no server)
4. On each message: embed your question → retrieve top 3–5 relevant chunks → include them in the prompt sent to Gemini
5. Add a simple command like `/remember <fact>` that saves a new fact directly into memory

**Deliverable:** Ziwena recalls facts about you across sessions.

## Phase 3 — Expand to real life-help (weeks 3–4)

Pick 1–2 domains at a time, don't build all at once:

| Domain | What to add |
|---|---|
| Daily planning | Simple task list stored in a JSON/SQLite file; Ziwena can add/list/complete tasks |
| Journaling | A `/journal` command that saves your entry and lets Ziwena reflect it back or ask a follow-up |
| Habits | A small tracker (habit name, streak count) Ziwena checks in on daily |
| Calendar | Connect Google Calendar API (read-only free tier) so Ziwena knows your schedule |

Each domain is just: a small data store + a few functions Ziwena can call ("tools"). This is where it becomes an *agent* rather than a chatbot — it can take actions, not just answer.

## Phase 4 — Give it a real interface (week 5)

1. `pip install streamlit`
2. Wrap the chat loop in a simple Streamlit UI — text input, chat history, sidebar showing memory/tasks
3. Run locally with `streamlit run app.py`

**Deliverable:** a proper chat app in your browser, not just a terminal.

## Phase 5 — Deploy it so it's reachable anywhere

Pick one:
- **Hugging Face Spaces** — free, connects to a GitHub repo, good for Streamlit apps
- **Telegram bot** — feels the most like a personal assistant; free hosting on Railway/Render's free tier
- **Railway/Render** — more control if you outgrow the free tiers above

Before going live:
- API key in environment variables (never committed to GitHub)
- Add a password/login if it's publicly reachable
- Make sure your vector DB folder is on **persistent** storage (many free hosts wipe disk on restart — check this explicitly)

## Phase 6 — Make it proactive (ongoing)

Once the reactive version works well:
- A daily scheduled job (cron, or a hosted scheduler) that has Ziwena message you each morning with a check-in
- Let it flag things itself: "you said you wanted to call your mom this week — did you?"
- Slowly expand its tools: email drafting, reminders, whatever your Phase 0 doc prioritized

## Suggested build order (if you want one linear path)

1. Phase 0 doc → 2. CLI chat loop → 3. Memory/RAG → 4. One life-domain (pick journaling or tasks) → 5. Streamlit UI → 6. Deploy as Telegram bot → 7. Add more domains over time

## Notes

- Free API tiers (Gemini, Groq) are enough for a personal project's volume — you won't hit limits doing normal daily use
- Keep everything you tell Ziwena in plain text files/SQLite at first — resist the urge to over-engineer the storage before you know what you actually need
- The system prompt (Ziwena's personality + rules) is the single highest-leverage file in the whole project — iterate on it more than the code
