import glob
import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

import ziwena_memory as memory
import ziwena_actions as actions

load_dotenv()

st.set_page_config(
    page_title="Ziwena — Mahdi's Personal Life Agent",
    page_icon="🤖",
    layout="wide",
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Uses whatever model is in .env; falls back to a generous, currently-stable
# alias if ZIWENA_MODEL isn't set. See list_models.py to check what your
# specific key can access if this ever 404s.
MODEL_NAME = os.getenv("ZIWENA_MODEL", "gemini-flash-lite-latest")
CV_DIR = os.path.join(os.path.dirname(__file__), "cv")


def find_cv_path():
    candidates = [
        os.path.join(CV_DIR, "CV_Mahdi_Bey.pdf"),
        os.path.join(CV_DIR, "CV_Mehdi_Bey.pdf"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path

    pdfs = sorted(glob.glob(os.path.join(CV_DIR, "*.pdf")))
    return pdfs[0] if pdfs else None


CV_PATH = find_cv_path()

if not GEMINI_API_KEY:
    st.error("GEMINI_API_KEY is not set. Add it to your .env file next to this script "
              "(GEMINI_API_KEY=your_key_here) and restart.")
    st.stop()

SYSTEM_PROMPT = """
You are Ziwena, a personal life assistant for Mahdi Bey (also called Mahdi
or "Mahden" as a nickname — respond naturally to any of these).

PERSONALITY:
- Direct: say what you actually think, don't sugarcoat or dodge.
- Gentle: deliver honest feedback with care, never harsh.
- Funny: have real personality, don't sound like a corporate assistant.
- You talk like a close, trusted friend who genuinely wants the best for
  Mahdi, not like a customer support bot. You can call him "Mahden" as a
  warm nickname sometimes, the way a close friend would.

LANGUAGES:
- You speak Tunisian Arabic dialect (Derja), English, French, and German fluently.
- Always detect the language/dialect Mahdi writes in and reply in the same one.
- If Mahdi writes in Tunisian Derja, even in Latin/Arabizi script
  (e.g. "chnowa akhbarek"), reply in Tunisian Derja, not Modern Standard Arabic.
- If Mahdi mixes languages in one message, match the dominant one.

WHAT YOU HELP WITH:
1. Scheduling and organizing daily/weekly life.
2. Learning new skills, studying, self-improvement.
3. Job search - finding Werkstudent jobs, applications, interview prep.
4. His relationship with his girlfriend - thoughtful, caring advice.
5. General self-improvement, like a friend who checks in and pushes him forward.

WEB SEARCH:
- You have live Google Search access. Use it whenever a question needs
  current or real-world info you wouldn't reliably know otherwise.
- When you use search results, mention briefly where the info is from.
- Don't mention searching for basic things you'd already know.

JOURNAL:
- Mahdi may keep a structured journal with /journal — reflective entries about
  mood, stress, progress on goals. When asked to /reflect, identify honest
  patterns: recurring stress points, mood trends, progress or lack of it.

MEMORY:
- You have long-term memory. Before some replies, you may be given
  relevant memories from past conversations — use them naturally.

BEHAVIOR RULE:
- Always tell Mahdi before doing anything and get his confirmation first.

FACTS ABOUT MEHDI:
- Hardworking, always wants to improve himself.
- Loves his family and his girlfriend deeply.
- Hobbies: tennis, football.
- Loves Turkish series.
- Currently training at the gym, working on getting in good shape.
- Lives in Köthen, Germany.
- Studying a Master's in Data Science at Hochschule Anhalt.
- Currently searching for a Werkstudent job, wants to work now alongside studies.
- Long-term goal: become a successful professional in data and ML.
"""


def init_chat():
    client = genai.Client(api_key=GEMINI_API_KEY)
    st.session_state.genai_client = client  # keep a live reference so it
    # never gets garbage-collected between Streamlit reruns
    try:
        chat = client.chats.create(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
    except Exception as e:
        st.error(
            f"Couldn't start Ziwena with model '{MODEL_NAME}': {e}\n\n"
            "Run list_models.py to see which model names your API key can "
            "actually access, then set ZIWENA_MODEL in .env accordingly."
        )
        st.stop()

    if CV_PATH and os.path.isfile(CV_PATH):
        try:
            cv_file_ref = client.files.upload(file=CV_PATH)
            chat.send_message([
                cv_file_ref,
                "This is my CV. Keep it in mind for the rest of our conversation "
                "whenever it's relevant (job search, applications, interview prep)."
            ])
            st.session_state.cv_status = f"Loaded ✅ ({os.path.basename(CV_PATH)})"
        except Exception as e:
            st.session_state.cv_status = f"Couldn't load ({e})"
    else:
        st.session_state.cv_status = f"Not found in {CV_DIR}"

    return chat


def get_cached_calendar(days: int = 7):
    now = datetime.now()
    if (
        "calendar_cache" not in st.session_state
        or "calendar_cache_time" not in st.session_state
        or (now - st.session_state.calendar_cache_time).total_seconds() > 900
    ):
        st.session_state.calendar_cache = actions.get_upcoming_events(days=days)
        st.session_state.calendar_cache_time = now
    return st.session_state.calendar_cache


def build_calendar_prompt(events):
    if not events:
        return ""
    lines = ["Here are your upcoming calendar events:"]
    for ev in events:
        lines.append(f"- {ev['summary']} from {ev['start']} to {ev['end']}")
    return "\n".join(lines)


def safe_send(parts):
    """
    Send a message to the chat, transparently recovering once if the
    underlying client was closed by a Streamlit rerun. Any real API error
    (quota, 429, etc.) is re-raised as-is so it displays exactly as Google
    sent it — no rewording.
    """
    try:
        return st.session_state.chat.send_message(parts)
    except Exception as e:
        if "client has been closed" in str(e).lower():
            st.session_state.chat = init_chat()
            return st.session_state.chat.send_message(parts)
        raise


def send_with_memory(user_text: str):
    relevant = memory.retrieve_relevant(user_text)
    calendar_events = get_cached_calendar()
    calendar_block = build_calendar_prompt(calendar_events)

    blocks = []
    if calendar_block:
        blocks.append(calendar_block)
    if relevant:
        memory_block = "\n".join(f"- {m}" for m in relevant)
        blocks.append(f"Relevant memories from before:\n{memory_block}")

    if blocks:
        full_message = "\n\n".join(blocks) + f"\n\nMahdi says: {user_text}"
    else:
        full_message = user_text

    with st.spinner("Ziwena is thinking...", show_time=True):
        response = safe_send(full_message)
    memory.add_memory(f"Mahdi said: {user_text}\nZiwena replied: {response.text}")

    if memory.needs_compaction():
        status = memory.compact_old_memories(st.session_state.genai_client, MODEL_NAME)
        if status:
            st.session_state.history.append(("system", status))

    return response.text


def render_sidebar():
    with st.sidebar:
        st.header("🤖 Ziwena")
        st.caption("Mahdi's personal life agent")
        st.markdown("---")
        st.markdown("**Agent state**")
        st.write(f"- Model: `{MODEL_NAME}`")
        st.write(f"- Memories: {memory.memory_count()}")
        st.write(f"- Journal entries: {memory.journal_count()}")
        if "cv_status" in st.session_state:
            st.write(f"- CV: {st.session_state.cv_status}")
        st.markdown("---")
        st.markdown("**Commands**")
        st.code(
            "/remember <fact>\n"
            "/journal <entry>\n"
            "/reflect [days]\n"
            "/calendar [days]\n"
            "/jobs <query>\n"
            "/myjobs\n"
            "/compact",
            language=None,
        )
        st.markdown("---")
        st.caption("For deployment: set GEMINI_API_KEY as an environment secret, not in code.")


if "history" not in st.session_state:
    st.session_state.history = []

if "chat" not in st.session_state:
    with st.spinner("Loading Ziwena... preparing your assistant, memory, and calendar.", show_time=True):
        st.session_state.chat = init_chat()

st.markdown("""
<style>
[data-testid="stStatusWidget"] {
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    background: rgba(255,255,255,0.02);
    padding: 0.2rem 0.5rem;
}
div[data-testid="stStatusWidget"] > div {
    align-items: center;
    gap: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

st.title("🤖 Ziwena")
st.caption("Ahla lmahden, winek sahbi, echkili fech najem n3awnek 👋")

render_sidebar()

chat_container = st.container()
with chat_container:
    for role, message in st.session_state.history:
        if role == "user":
            st.chat_message("user").write(message)
        elif role == "assistant":
            st.chat_message("assistant").write(message)
        else:
            st.info(message)

st.markdown("---")

# Align the mic button with the chat input's height and remove the visual
# gap between them so they read as one connected control, ChatGPT-style.
st.markdown("""
<style>
[data-testid="stAudioInput"] {
    height: 100%;
}
[data-testid="stAudioInput"] > div {
    height: 52px;
    display: flex;
    align-items: center;
}
div[data-testid="column"]:has([data-testid="stAudioInput"]) {
    margin-left: -8px;
}
</style>
""", unsafe_allow_html=True)

input_col, mic_col = st.columns([6, 1], gap="small")

with input_col:
    user_input = st.chat_input(
        "Ekteb l Ziwena...",
        accept_file="multiple",
        file_type=["png", "jpg", "jpeg", "pdf", "docx", "txt"],
    )

with mic_col:
    voice_note = st.audio_input("🎤", label_visibility="collapsed")

# ---------- Handle an uploaded voice note ----------
if voice_note is not None and voice_note != st.session_state.get("last_voice_note"):
    st.session_state.last_voice_note = voice_note
    st.session_state.history.append(("user", "🎤 [voice message]"))
    try:
        audio_part = types.Part.from_bytes(
            data=voice_note.getvalue(),
            mime_type="audio/wav",
        )
        with st.spinner("Listening to your voice note and replying...", show_time=True):
            response = safe_send([
                audio_part,
                "This is a voice message from Mahdi. Transcribe it mentally and "
                "reply naturally in whatever language he spoke, following your "
                "usual personality.",
            ])
        reply = response.text
    except Exception as e:
        reply = f"[Error handling voice message: {e}]"
    st.session_state.history.append(("assistant", reply))
    st.rerun()

# ---------- Handle files attached via the chat input's paperclip icon ----------
attached_files = user_input.files if user_input else []
attached_text = user_input.text.strip() if user_input else ""

if attached_files:
    for f in attached_files:
        st.session_state.history.append(("user", f"📎 [attached: {f.name}]"))
        try:
            tmp_path = os.path.join("uploads_tmp", f.name)
            os.makedirs("uploads_tmp", exist_ok=True)
            with open(tmp_path, "wb") as out:
                out.write(f.getvalue())
            file_ref = st.session_state.genai_client.files.upload(file=tmp_path)
            parts = [file_ref]
            if attached_text:
                parts.append(attached_text)
            else:
                parts.append(
                    f"Mahdi just shared this file ({f.name}). Take a look and "
                    "give your honest first thoughts on it, or ask what he "
                    "wants you to do with it if that's not obvious."
                )
            with st.spinner(f"Reviewing {f.name}...", show_time=True):
                response = safe_send(parts)
            reply = response.text
        except Exception as e:
            reply = f"[Error handling file '{f.name}': {e}]"
        st.session_state.history.append(("assistant", reply))
    st.rerun()

if attached_text:
    if attached_text.startswith("/remember "):
        fact = attached_text[len("/remember "):].strip()
        memory.add_memory(fact)
        st.session_state.history.append(("assistant", f"Sajjelt! ✅ (\"{fact}\")"))
    elif attached_text.startswith("/journal "):
        entry = attached_text[len("/journal "):].strip()
        memory.add_journal_entry(entry)
        st.session_state.history.append(("assistant", f"Journal entry saved. ✅ ({memory.journal_count()} entries total)"))
    elif attached_text == "/reflect" or attached_text.startswith("/reflect "):
        days_str = attached_text[len("/reflect"):].strip()
        days = int(days_str) if days_str.isdigit() else 30
        entries = memory.get_journal_entries_since(days=days)
        if not entries:
            st.session_state.history.append(("assistant", f"No journal entries in the last {days} days yet. Use /journal <entry> to start."))
        else:
            entries_text = "\n".join(f"[{ts[:10]}] {text}" for ts, text in entries)
            reflect_prompt = (
                f"Here are my journal entries from the last {days} days:\n\n"
                f"{entries_text}\n\n"
                "Reflect back any patterns you notice — mood trends, recurring "
                "stress points, progress (or lack of it) on my goals. Be honest "
                "and direct, like you always are."
            )
            with st.spinner("Checking your journal patterns...", show_time=True):
                response = safe_send(reflect_prompt)
            st.session_state.history.append(("assistant", response.text))
    elif attached_text == "/calendar" or attached_text.startswith("/calendar "):
        days_str = attached_text[len("/calendar"):].strip()
        days = int(days_str) if days_str.isdigit() else 7
        events = actions.get_upcoming_events(days=days)
        st.session_state.history.append(("assistant", actions.format_events(events)))
    elif attached_text.startswith("/jobs "):
        query = attached_text[len("/jobs "):].strip()
        st.session_state.history.append(("assistant", "Searching for real postings..."))
        with st.spinner("Looking through current job listings...", show_time=True):
            result = actions.search_and_shortlist_jobs(st.session_state.chat, query)
        st.session_state.history.append(("assistant", result))
    elif attached_text == "/myjobs":
        st.session_state.history.append(("assistant", actions.list_saved_jobs()))
    elif attached_text == "/compact":
        status = memory.compact_old_memories(st.session_state.genai_client, MODEL_NAME)
        st.session_state.history.append(("assistant", status or "[Nothing to compact yet.]"))
    else:
        st.session_state.history.append(("user", attached_text))
        try:
            reply = send_with_memory(attached_text)
        except Exception as e:
            reply = f"[Error talking to Gemini: {e}]"
        st.session_state.history.append(("assistant", reply))
    st.rerun()