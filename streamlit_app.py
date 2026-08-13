import glob
import json
import os
import time
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
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

# ---------- Lock screen (hardcoded 6-digit PIN) ----------
# TODO: move this to .env (ZIWENA_LOCK_CODE) before sharing/deploying this
# app anywhere — a hardcoded PIN in source code is fine for local personal
# use only, not for a publicly reachable deployment.
LOCK_CODE = "200145"

st.markdown("""
<style>
/* ---------- Responsive base ---------- */
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 1rem;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
    max-width: 900px;
}
@media (max-width: 640px) {
    .block-container {
        padding-left: 0.75rem;
        padding-right: 0.75rem;
        padding-top: 0.75rem;
    }
    h1 { font-size: 1.5rem !important; }
    [data-testid="stSidebar"] { width: 80vw !important; }
}

/* ---------- Lock screen ---------- */
.lock-wrap {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 1rem;
    width: 100%;
    max-width: 320px;
}
.lock-icon {
    font-size: 2.75rem;
    margin-bottom: 0.5rem;
}
.lock-title {
    font-size: 1.4rem;
    font-weight: 700;
    margin-bottom: 0.15rem;
}
.lock-subtitle {
    font-size: 0.92rem;
    opacity: 0.65;
    margin-bottom: 1.75rem;
}
.lock-boxes {
    display: flex;
    gap: 0.6rem;
    justify-content: center;
    margin-bottom: 1.5rem;
}
.lock-box {
    width: 40px;
    height: 48px;
    border: 2px solid rgba(128,128,128,0.45);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.3rem;
    font-weight: 700;
    color: inherit;
}
.lock-box.filled {
    border-color: currentColor;
}
.lock-or {
    font-size: 0.8rem;
    opacity: 0.5;
    margin: 0.9rem 0;
    text-transform: uppercase;
    letter-spacing: 0.1rem;
}
.lock-wrap [data-testid="stTextInput"] input {
    text-align: center;
    font-size: 1.4rem;
    letter-spacing: 0.5rem;
    font-weight: 600;
    padding: 0.6rem 0.5rem;
    border-radius: 12px;
}
.lock-error {
    color: #ff6b6b;
    font-size: 0.85rem;
    margin-bottom: 1rem;
    min-height: 1.2rem;
}
.lock-keypad {
    max-width: 260px;
    margin: 0 auto;
}
.lock-keypad .stButton button {
    width: 100%;
    aspect-ratio: 1 / 1;
    border-radius: 50%;
    font-size: 1.3rem;
    font-weight: 600;
    padding: 0;
    margin-bottom: 0.6rem;
}

/* ---------- Skeleton loader ---------- */
@keyframes ziwena-pulse {
    0% { opacity: 0.55; }
    50% { opacity: 1; }
    100% { opacity: 0.55; }
}
.ziwena-skeleton {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.75rem 0;
}
.ziwena-skeleton .sk-line {
    height: 14px;
    border-radius: 7px;
    background: rgba(128,128,128,0.25);
    animation: ziwena-pulse 1.2s ease-in-out infinite;
}
.ziwena-skeleton .sk-avatar-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
}
.ziwena-skeleton .sk-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: rgba(128,128,128,0.3);
    animation: ziwena-pulse 1.2s ease-in-out infinite;
    flex-shrink: 0;
}
.ziwena-skeleton .sk-bubble {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
}
.lock-keypad [data-testid="stHorizontalBlock"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 0.6rem;
    width: 100%;
}
.lock-keypad [data-testid="stHorizontalBlock"] > div {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    width: 100% !important;
    gap: 0.6rem;
}
.lock-keypad [data-testid="stColumn"],
.lock-keypad [data-testid="column"] {
    width: 33.33% !important;
    flex: 1 1 0 !important;
    min-width: 0 !important;
}
@media (max-width: 640px) {
    .lock-keypad [data-testid="stHorizontalBlock"],
    .lock-keypad [data-testid="stHorizontalBlock"] > div {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
    }
    .lock-keypad [data-testid="stColumn"],
    .lock-keypad [data-testid="column"] {
        width: 33.33% !important;
        flex: 1 1 0 !important;
    }
    .lock-keypad .stButton button {
        font-size: 1.1rem;
    }
}
</style>
""", unsafe_allow_html=True)


def render_skeleton(lines=2, avatar=True):
    """Render a pulsing skeleton block (used instead of/with a spinner)."""
    widths = ["70%", "45%", "85%", "60%"]
    row_html = "".join(
        f'<div class="sk-line" style="width:{widths[i % len(widths)]}"></div>'
        for i in range(lines)
    )
    if avatar:
        html = (
            '<div class="ziwena-skeleton"><div class="sk-avatar-row">'
            f'<div class="sk-avatar"></div><div class="sk-bubble">{row_html}</div>'
            '</div></div>'
        )
    else:
        html = f'<div class="ziwena-skeleton">{row_html}</div>'
    return st.markdown(html, unsafe_allow_html=True)


def render_lock_screen():
    if "pin_entry" not in st.session_state:
        st.session_state.pin_entry = ""
    if "pin_error" not in st.session_state:
        st.session_state.pin_error = ""

    def press(digit):
        # Only append the digit here — do NOT check/unlock yet. If we
        # unlocked inside this callback, the script would skip straight
        # past render_lock_screen() on the very next run and the 6th box
        # would never actually be shown on screen.
        if len(st.session_state.pin_entry) < 6:
            st.session_state.pin_entry += digit
            st.session_state.pin_error = ""

    def backspace():
        st.session_state.pin_entry = st.session_state.pin_entry[:-1]
        st.session_state.pin_error = ""

    def on_text_change():
        digits = "".join(ch for ch in st.session_state.pin_text_input if ch.isdigit())[:6]
        st.session_state.pin_entry = digits
        st.session_state.pin_error = ""

    st.markdown('<div class="lock-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="lock-icon">🔒</div>', unsafe_allow_html=True)
    st.markdown('<div class="lock-title">Ziwena is locked</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="lock-subtitle">Enter your 6-digit code to continue</div>',
        unsafe_allow_html=True,
    )

    boxes_html = "".join(
        f'<div class="lock-box{" filled" if i < len(st.session_state.pin_entry) else ""}">'
        f'{st.session_state.pin_entry[i] if i < len(st.session_state.pin_entry) else ""}'
        f'</div>'
        for i in range(6)
    )
    st.markdown(f'<div class="lock-boxes">{boxes_html}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="lock-error">{st.session_state.pin_error}</div>',
        unsafe_allow_html=True,
    )

    # Option 1: clickable numeric keypad
    st.markdown('<div class="lock-keypad">', unsafe_allow_html=True)
    rows = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["", "0", "⌫"]]
    for row in rows:
        cols = st.columns(3, gap="small")
        for col, key in zip(cols, row):
            with col:
                if key == "":
                    st.write("")
                elif key == "⌫":
                    st.button("⌫", key="lock_back", on_click=backspace, use_container_width=True)
                else:
                    st.button(key, key=f"lock_{key}", on_click=press, args=(key,), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Option 2: type the code directly with the keyboard
    st.markdown('<div class="lock-or">or type it</div>', unsafe_allow_html=True)
    st.text_input(
        "code_text",
        max_chars=6,
        type="password",
        label_visibility="collapsed",
        placeholder="••••••",
        key="pin_text_input",
        value=st.session_state.pin_entry,
        on_change=on_text_change,
    )

    st.markdown('</div>', unsafe_allow_html=True)

    # By this point the 6th box has already been drawn above (with the
    # digit visible), so it's safe to now check the code and, only after
    # a brief pause, move on.
    if len(st.session_state.pin_entry) == 6:
        if st.session_state.pin_entry == LOCK_CODE:
            time.sleep(0.35)  # let the last digit register visually first
            st.session_state.unlocked = True
            st.rerun()
        else:
            time.sleep(0.35)
            st.session_state.pin_error = "Wrong code. Try again."
            st.session_state.pin_entry = ""
            st.rerun()


if "unlocked" not in st.session_state:
    st.session_state.unlocked = False

if not st.session_state.unlocked:
    st.markdown("""
    <style>
    .block-container {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    header[data-testid="stHeader"] {
        height: 0;
    }
    html, body, [data-testid="stAppViewContainer"] {
        overflow: hidden !important;
    }
    </style>
    """, unsafe_allow_html=True)
    render_lock_screen()
    st.stop()
# ---------- End lock screen ----------



GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Uses whatever model is in .env; falls back to a generous, currently-stable
# alias if ZIWENA_MODEL isn't set. See list_models.py to check what your
# specific key can access if this ever 404s.
MODEL_NAME = os.getenv("ZIWENA_MODEL", "gemini-flash-lite-latest")
# Model lineup as of Aug 2026. If the current model gets rate-limited,
# fall back to these (all currently GA, non-preview) in order. Update this
# list if Google deprecates any of these — check
# https://ai.google.dev/gemini-api/docs/models for the current lineup.
MODEL_FALLBACKS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash"]
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
- You have live Google Search access and standing permission to use it
  whenever a question needs current or real-world info — never ask
  Mahdi for permission first, just search and answer.
- When you use search results, mention briefly where the info is from.
- Don't mention searching for basic things you'd already know.
- The current date/time is given to you directly in context on every
  message (see "Right now:" below) — never search or ask for today's
  date, just read it from there.

JOURNAL:
- Mahdi may keep a structured journal with /journal — reflective entries about
  mood, stress, progress on goals. When asked to /reflect, identify honest
  patterns: recurring stress points, mood trends, progress or lack of it.

MEMORY:
- You have long-term memory. Before some replies, you may be given
  relevant memories from past conversations — use them naturally.

BEHAVIOR RULE:
- Answering questions (including looking things up via search) needs NO
  permission — just answer directly and naturally, like a friend would.
- Only ask for confirmation before things that actually change something
  or commit Mahdi to something: adding a calendar event, saving a memory
  or journal entry on his behalf, applying to a job, or similar actions.

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


CV_UPLOAD_STATE_FILE = os.path.join(os.path.dirname(__file__), ".cv_upload_state.json")


def _load_cv_upload_state():
    try:
        with open(CV_UPLOAD_STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cv_upload_state(file_name, cv_path):
    try:
        with open(CV_UPLOAD_STATE_FILE, "w") as f:
            json.dump({
                "file_name": file_name,
                "cv_path": cv_path,
                "cv_mtime": os.path.getmtime(cv_path),
            }, f)
    except Exception:
        pass  # tracking is a best-effort optimization, never fatal


def get_or_upload_cv(client, cv_path):
    """Reuse the previously uploaded CV file on Gemini's servers instead of
    re-uploading it every app restart. Falls back to a fresh upload if no
    record exists, the CV file changed, or the remembered file expired."""
    state = _load_cv_upload_state()
    if state and state.get("cv_path") == cv_path:
        if state.get("cv_mtime") == os.path.getmtime(cv_path):
            try:
                existing = client.files.get(name=state["file_name"])
                return existing  # reused — no upload call made
            except Exception:
                pass  # file expired or missing on Gemini's side — re-upload below

    uploaded = client.files.upload(file=cv_path)
    _save_cv_upload_state(uploaded.name, cv_path)
    return uploaded


def init_chat():
    global MODEL_NAME
    client = genai.Client(api_key=GEMINI_API_KEY)
    st.session_state.genai_client = client  # keep a live reference so it
    # never gets garbage-collected between Streamlit reruns

    models_to_try = [MODEL_NAME] + [m for m in MODEL_FALLBACKS if m != MODEL_NAME]
    chat = None
    last_error = None
    for candidate in models_to_try:
        try:
            chat = client.chats.create(
                model=candidate,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            if candidate != MODEL_NAME:
                st.session_state.history = st.session_state.get("history", [])
                st.session_state.history.append(
                    ("system", f"[Started Ziwena on '{candidate}' — '{MODEL_NAME}' wasn't available.]")
                )
            MODEL_NAME = candidate
            st.session_state.tried_models = {candidate}
            break
        except Exception as e:
            last_error = e
            continue

    if chat is None:
        st.error(
            f"Couldn't start Ziwena with model '{MODEL_NAME}' or any fallback: {last_error}\n\n"
            "Run list_models.py to see which model names your API key can "
            "actually access, then set ZIWENA_MODEL in .env accordingly."
        )
        st.stop()

    if CV_PATH and os.path.isfile(CV_PATH):
        st.session_state.cv_status = f"Available but not auto-loaded ({os.path.basename(CV_PATH)})"
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


def _is_quota_error(e) -> bool:
    s = str(e).lower()
    return "429" in s or "resource_exhausted" in s or "quota" in s


def _is_unavailable_error(e) -> bool:
    s = str(e).lower()
    return (
        _is_quota_error(e)
        or "404" in s
        or "not_found" in s
        or "no longer available" in s
    )


def _switch_to_fallback_model():
    """Rebuild the chat on the next working model in MODEL_FALLBACKS,
    carrying the existing conversation history over so context isn't lost.
    If a candidate itself is unavailable (e.g. deprecated/404), skip it and
    try the next one rather than failing outright."""
    global MODEL_NAME
    tried = st.session_state.get("tried_models", {MODEL_NAME})

    try:
        history = st.session_state.chat.get_history()
    except Exception:
        history = None

    client = st.session_state.genai_client

    for candidate in MODEL_FALLBACKS:
        if candidate in tried:
            continue
        tried.add(candidate)
        st.session_state.tried_models = tried
        try:
            new_chat = client.chats.create(
                model=candidate,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                history=history,
            )
        except Exception:
            continue  # this candidate itself is unavailable — try the next one

        st.session_state.chat = new_chat
        MODEL_NAME = candidate
        st.session_state.history.append(
            ("system", f"[Switched to '{candidate}' — the previous model's free quota was exhausted.]")
        )
        return True

    return False  # nothing left to try


def response_text(response):
    """response_text(response) can be None (e.g. a grounded/search turn that only
    returned metadata) — never let that leak to the user as the string
    'None'."""
    text = getattr(response, "text", None)
    if text:
        return text
    return ("Hmm, I got an empty reply back from Gemini that time — can you "
            "ask that again? (Mahden, 3awed el message.)")


def safe_send(parts, _attempt=0):
    """
    Send a message to the chat, transparently recovering from:
      - a client closed by a Streamlit rerun (re-init and retry once)
      - 429 / quota-exhausted errors (short backoff retry, then fall back
        to the next model in MODEL_FALLBACKS if retries are still exhausted)
      - 404 / model-no-longer-available errors (fall back immediately —
        retrying the same dead model won't help)
    Any other error is re-raised as-is so it displays exactly as Google
    sent it — no rewording.
    """
    try:
        return st.session_state.chat.send_message(parts)
    except Exception as e:
        if "client has been closed" in str(e).lower():
            st.session_state.chat = init_chat()
            return st.session_state.chat.send_message(parts)

        if _is_quota_error(e):
            if _attempt < 2:
                time.sleep(2 * (_attempt + 1))  # 2s, then 4s backoff
                return safe_send(parts, _attempt=_attempt + 1)
            if _switch_to_fallback_model():
                return safe_send(parts, _attempt=0)
        elif _is_unavailable_error(e):
            # 404 / deprecated model — no point retrying the same one,
            # jump straight to the next fallback.
            if _switch_to_fallback_model():
                return safe_send(parts, _attempt=0)

        raise


def send_with_memory(user_text: str):
    relevant = memory.retrieve_relevant(user_text)
    calendar_events = get_cached_calendar()
    calendar_block = build_calendar_prompt(calendar_events)

    now = datetime.now()
    time_block = f"Right now: {now.strftime('%A, %d %B %Y, %H:%M')} (Köthen, Germany time)."

    blocks = [time_block]
    if calendar_block:
        blocks.append(calendar_block)
    if relevant:
        memory_block = "\n".join(f"- {m}" for m in relevant)
        blocks.append(f"Relevant memories from before:\n{memory_block}")

    full_message = "\n\n".join(blocks) + f"\n\nMahdi says: {user_text}"

    response = safe_send(full_message)
    memory.add_memory(f"Mahdi said: {user_text}\nZiwena replied: {response_text(response)}")

    if memory.needs_compaction():
        status = memory.compact_old_memories(st.session_state.genai_client, MODEL_NAME)
        if status:
            st.session_state.history.append(("system", status))

    return response_text(response)


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
    skeleton_slot = st.empty()
    with skeleton_slot.container():
        render_skeleton(lines=3, avatar=True)
        render_skeleton(lines=2, avatar=True)
    st.session_state.chat = init_chat()
    skeleton_slot.empty()

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
    st.markdown('<div id="ziwena-bottom-anchor"></div>', unsafe_allow_html=True)

components.html("""
<script>
    var doc = window.parent.document;
    var anchor = doc.getElementById("ziwena-bottom-anchor");
    if (anchor) { anchor.scrollIntoView({behavior: "smooth", block: "end"}); }
</script>
""", height=0)

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
@media (max-width: 640px) {
    [data-testid="stAudioInput"] > div {
        height: 44px;
    }
    div[data-testid="column"]:has([data-testid="stAudioInput"]) {
        margin-left: -4px;
    }
    [data-testid="stChatInput"] textarea {
        font-size: 0.95rem;
    }
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
    with chat_container:
        st.chat_message("user").write("🎤 [voice message]")
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
        reply = response_text(response)
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
        with chat_container:
            st.chat_message("user").write(f"📎 [attached: {f.name}]")
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
            reply = response_text(response)
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
            st.session_state.history.append(("assistant", response_text(response)))
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
        with chat_container:
            st.chat_message("user").write(attached_text)
            thinking_slot = st.empty()
            with thinking_slot.container():
                render_skeleton(lines=2, avatar=True)
        try:
            reply = send_with_memory(attached_text)
        except Exception as e:
            reply = f"[Error talking to Gemini: {e}]"
        st.session_state.history.append(("assistant", reply))
    st.rerun()