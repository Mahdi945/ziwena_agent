"""
Ziwena — Phase 1 + 2: core chat loop + long-term RAG memory
Run with: python ziwena_phase1.py
Type 'quit' or 'exit' to end the conversation.

Commands:
  /image <path>        analyze an image
  /file <path>          analyze any file (PDF, docs, etc.)
  /generate <prompt>    generate an image (needs paid Imagen tier)
  /remember <fact>       save something permanently to long-term memory
  /journal <entry>       save a reflective journal entry (mood, thoughts, progress)
  /reflect [days]         ask Ziwena to summarize patterns from your journal
                          (default: last 30 days)
  /calendar [days]        show upcoming calendar events (default: next 7 days)
  /jobs <query>           search live Werkstudent postings and save new ones
  /myjobs                 list previously saved/shortlisted jobs
  /compact                manually compact old memories into a summary now
  /listen                 speak into your mic; Ziwena replies as text
  /voice                  toggle voice mode (spoken replies via TTS, on top of text)
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

import ziwena_memory as memory
import ziwena_actions as actions
import ziwena_audio as audio
from ziwena_scheduler import start_scheduler

# ---------- Load API key and model name from .env ----------
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("ZIWENA_MODEL", "gemini-2.5-flash-lite")

if not api_key:
    print("ERROR: GEMINI_API_KEY not found. Check your .env file.")
    sys.exit(1)

client = genai.Client(api_key=api_key)

# ---------- Mehdi's CV: repo-relative path, loaded automatically at startup ----------
CV_PATH = os.path.join(os.path.dirname(__file__), "cv", "CV_Mehdi_Bey.pdf")

cv_file_ref = None
if os.path.isfile(CV_PATH):
    try:
        cv_file_ref = client.files.upload(file=CV_PATH)
        print(f"[Loaded CV from {CV_PATH}]")
    except Exception as e:
        print(f"[Could not load CV: {e}]")
else:
    print(f"[CV not found at {CV_PATH} — Ziwena will start without it]")

print(f"[Long-term memory: {memory.memory_count()} memories stored so far]")
print(f"[Journal: {memory.journal_count()} entries stored so far]")

voice_mode = False  # toggled with /voice; when on, replies are also spoken

# ---------- Ziwena's personality (from Phase 0) ----------
SYSTEM_PROMPT = """
You are Ziwena, a personal life assistant for Mehdi Bey.

PERSONALITY:
- Direct: say what you actually think, don't sugarcoat or dodge.
- Gentle: deliver honest feedback with care, never harsh.
- Funny: have real personality, don't sound like a corporate assistant.
- You talk like a close, trusted friend who genuinely wants the best for Mehdi,
  not like a customer support bot.

LANGUAGES:
- You speak Tunisian Arabic dialect (Derja), English, French, and German fluently.
- Always detect the language/dialect Mehdi writes in and reply in the same one.
- If Mehdi writes in Tunisian Derja, even in Latin/Arabizi script
  (e.g. "chnowa akhbarek"), reply in Tunisian Derja, not Modern Standard Arabic.
- If Mehdi mixes languages in one message, match the dominant one.
- If Mehdi explicitly asks to switch language, switch immediately.
- Default to Arabic script for Derja, unless Mehdi writes in Arabizi/Latin script,
  in which case match that.

WHAT YOU HELP WITH:
1. Scheduling and organizing daily/weekly life.
2. Learning new skills, studying, self-improvement.
3. Job search - finding Werkstudent jobs, applications, interview prep.
   You have Mehdi's CV available (uploaded at startup) - use it whenever
   relevant, e.g. tailoring applications, suggesting roles, prepping for
   interviews. Refer to real details from it, don't guess.
4. His relationship with his girlfriend - thoughtful, caring advice.
5. General self-improvement, like a friend who checks in and pushes him forward.

WEB SEARCH:
- You have live Google Search access. Use it whenever a question needs
  current or real-world info you wouldn't reliably know otherwise —
  actual Werkstudent job postings, current interview trends, news, prices,
  deadlines, etc.
- When you use search results, mention briefly where the info is from
  (e.g. "found this on LinkedIn/Indeed") so Mehdi knows it's real and current,
  not something you're guessing.
- Don't mention searching for basic things you'd already know (definitions,
  general advice, casual chat).

JOURNAL:
- Mehdi may keep a structured journal with /journal — reflective entries about
  mood, stress, progress on goals. When asked to /reflect, look at the entries
  given to you and identify honest patterns: recurring stressors, mood trends,
  progress or lack of it on stated goals. Be direct but gentle, like a friend
  who's paying attention, not a therapist doing a clinical writeup.

MEMORY:
- You have long-term memory. Before some of your replies, you'll be given
  "Relevant memories" retrieved from past conversations - use them naturally
  if relevant, don't just recite them robotically. If nothing relevant is
  given, that's fine, just answer normally.

BEHAVIOR RULE:
- Always tell Mehdi before doing anything (sending messages, booking things,
  taking any action) and get his confirmation first. Never act unilaterally.

FACTS ABOUT MEHDI (use naturally when relevant, don't recite them robotically):
- Hardworking, always wants to improve himself.
- Loves his family and his girlfriend deeply.
- Hobbies: tennis, football.
- Loves Turkish series.
- Currently training at the gym, working on getting in good shape.
- Lives in Kothen, Germany.
- Studying a Master's in Data Science at Hochschule Anhalt.
- Currently searching for a Werkstudent job, wants to work now alongside studies.
- Long-term goal: become a successful professional in data and ML.
"""

# ---------- Set up chat session (keeps history automatically) ----------
chat = client.chats.create(
    model=model_name,
    config=types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(google_search=types.GoogleSearch())],
    ),
)

# If the CV loaded successfully, tell Ziwena about it right away.
if cv_file_ref is not None:
    try:
        chat.send_message([
            cv_file_ref,
            "This is my CV. Keep it in mind for the rest of our conversation "
            "whenever it's relevant (job search, applications, interview prep). "
            "Just confirm briefly that you've got it, don't summarize it yet."
        ])
    except Exception as e:
        print(f"[Could not send CV into chat context: {e}]")


calendar_cache = None
calendar_cache_time = None
CALENDAR_CACHE_TTL = 60 * 15  # refresh every 15 minutes


def get_cached_calendar(days: int = 7):
    global calendar_cache, calendar_cache_time
    now = datetime.now()
    if calendar_cache is None or calendar_cache_time is None or (now - calendar_cache_time).total_seconds() > CALENDAR_CACHE_TTL:
        events = actions.get_upcoming_events(days=days)
        calendar_cache = events
        calendar_cache_time = now
    return calendar_cache


def build_calendar_prompt(events):
    if not events:
        return ""
    lines = ["Here are your upcoming calendar events:"]
    for ev in events:
        lines.append(f"- {ev['summary']} from {ev['start']} to {ev['end']}")
    return "\n".join(lines)


def send_with_memory(user_text: str):
    """Retrieve relevant memories, inject them, then send the real message."""
    relevant = memory.retrieve_relevant(user_text)
    calendar_events = get_cached_calendar()
    calendar_block = build_calendar_prompt(calendar_events)

    prefix_parts = []
    if calendar_block:
        prefix_parts.append(calendar_block)
    if relevant:
        memory_block = "\n".join(f"- {m}" for m in relevant)
        prefix_parts.append(f"Relevant memories from before:\n{memory_block}")

    if prefix_parts:
        prefix = "\n\n".join(prefix_parts)
        full_message = f"{prefix}\n\nMehdi says: {user_text}"
    else:
        full_message = user_text

    response = chat.send_message(full_message)

    # Store this exchange automatically so all conversations are remembered,
    # not just things saved with /remember.
    memory.add_memory(f"Mehdi said: {user_text}\nZiwena replied: {response.text}")

    # Keep memory lean: once raw memories pile up, fold the old ones into a
    # summary in the background of this turn (cheap check first, model call
    # only if actually needed).
    if memory.needs_compaction():
        status = memory.compact_old_memories(client, model_name)
        if status:
            print(status)

    return response.text


def daily_checkin():
    """Called on a schedule (see start_scheduler below) — Ziwena reaches out first."""
    events = get_cached_calendar(days=7)
    calendar_block = build_calendar_prompt(events)
    prompt = (
        "It's time for your daily check-in with Mehdi. Greet him briefly, ask "
        "how he's doing today, and if relevant nudge him gently about anything "
        "outstanding you know about (job search, gym, studies) — keep it short, "
        "like a text from a friend, not a report."
    )
    if calendar_block:
        prompt = f"{calendar_block}\n\n{prompt}"
    try:
        response = chat.send_message(prompt)
        print(f"\n[Daily check-in] Ziwena: {response.text}\n")
        if voice_mode:
            audio.speak(response.text)
    except Exception as e:
        print(f"\n[Daily check-in failed: {e}]\n")


def handle_image_analysis(path):
    if not os.path.isfile(path):
        print(f"\n[Couldn't find that file: {path}]\n")
        return
    question = input("What do you want to ask about this image? ").strip()
    if not question:
        question = "What do you see in this image?"
    try:
        img = Image.open(path)
        response = chat.send_message([img, question])
        print(f"\nZiwena: {response.text}\n")
    except Exception as e:
        print(f"\n[Error analyzing image: {e}]\n")


def handle_file_analysis(path):
    if not os.path.isfile(path):
        print(f"\n[Couldn't find that file: {path}]\n")
        return
    question = input("What do you want to ask about this file? ").strip()
    if not question:
        question = "What is this file about?"
    try:
        uploaded = client.files.upload(file=path)
        response = chat.send_message([uploaded, question])
        print(f"\nZiwena: {response.text}\n")
    except Exception as e:
        print(f"\n[Error analyzing file: {e}]\n")


def handle_image_generation(prompt):
    try:
        result = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(number_of_images=1),
        )
        out_path = "ziwena_generated.png"
        result.generated_images[0].image.save(out_path)
        print(f"\nZiwena: Sahit, done! Saved the image as '{out_path}'.\n")
    except Exception as e:
        print(f"\n[Error generating image: {e}]")
        print("[Note: image generation needs a paid Google Cloud tier — "
              "chat, image analysis, and file analysis stay free either way.]\n")


# ---------- Chat loop ----------
def main():
    global voice_mode

    start_scheduler(on_checkin=daily_checkin, at_time=os.getenv("ZIWENA_CHECKIN_TIME", "09:00"))

    print("\nZiwena is ready. Type 'quit' or 'exit' to stop.")
    print("Commands: /image <path> | /file <path> | /generate <desc> | /remember <fact>")
    print("          /calendar [days] | /jobs <query> | /myjobs | /compact | /listen | /voice\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nZiwena: aya beslema lmahden")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("Ziwena: aya beslema lmahden")
            break

        if user_input.startswith("/image "):
            handle_image_analysis(user_input[len("/image "):].strip())
            continue

        if user_input.startswith("/file "):
            handle_file_analysis(user_input[len("/file "):].strip())
            continue

        if user_input.startswith("/generate "):
            handle_image_generation(user_input[len("/generate "):].strip())
            continue

        if user_input.startswith("/remember "):
            fact = user_input[len("/remember "):].strip()
            memory.add_memory(fact)
            print(f"\nZiwena: Sajjelt! ✅ (\"{fact}\")\n")
            continue

        if user_input.startswith("/journal "):
            entry = user_input[len("/journal "):].strip()
            memory.add_journal_entry(entry)
            print(f"\nZiwena: Journal entry saved. ✅ ({memory.journal_count()} entries total)\n")
            continue

        if user_input == "/reflect" or user_input.startswith("/reflect "):
            days_str = user_input[len("/reflect"):].strip()
            days = int(days_str) if days_str.isdigit() else 30

            entries = memory.get_journal_entries_since(days=days)
            if not entries:
                print(f"\nZiwena: No journal entries in the last {days} days yet. "
                      f"Use /journal <entry> to start.\n")
                continue

            entries_text = "\n".join(
                f"[{ts[:10]}] {text}" for ts, text in entries
            )
            reflect_prompt = (
                f"Here are my journal entries from the last {days} days:\n\n"
                f"{entries_text}\n\n"
                f"Reflect back any patterns you notice — mood trends, recurring "
                f"stress points, progress (or lack of it) on my goals. Be honest "
                f"and direct, like you always are."
            )
            try:
                response = chat.send_message(reflect_prompt)
                print(f"\nZiwena: {response.text}\n")
            except Exception as e:
                print(f"\n[Error reflecting on journal: {e}]\n")
            continue

        if user_input == "/calendar" or user_input.startswith("/calendar "):
            days_str = user_input[len("/calendar"):].strip()
            days = int(days_str) if days_str.isdigit() else 7
            events = actions.get_upcoming_events(days=days)
            print(f"\nZiwena:\n{actions.format_events(events)}\n")
            continue

        if user_input.startswith("/jobs "):
            query = user_input[len("/jobs "):].strip()
            print("\n[Searching for real postings — this hits live web search...]")
            result = actions.search_and_shortlist_jobs(chat, query)
            print(f"\nZiwena:\n{result}\n")
            continue

        if user_input == "/myjobs":
            print(f"\nZiwena:\n{actions.list_saved_jobs()}\n")
            continue

        if user_input == "/compact":
            status = memory.compact_old_memories(client, model_name)
            print(f"\n{status or '[Nothing to compact yet.]'}\n")
            continue

        if user_input == "/listen":
            heard = audio.listen()
            if not heard:
                continue
            try:
                reply = send_with_memory(heard)
                print(f"\nZiwena: {reply}\n")
                audio.speak(reply)
            except Exception as e:
                print(f"\n[Error talking to Gemini: {e}]\n")
            continue

        if user_input == "/voice":
            voice_mode = not voice_mode
            print(f"\n[Voice mode {'ON — replies will be spoken' if voice_mode else 'OFF'}]\n")
            continue

        try:
            reply = send_with_memory(user_input)
            print(f"\nZiwena: {reply}\n")
            if voice_mode:
                audio.speak(reply)
        except Exception as e:
            print(f"\n[Error talking to Gemini: {e}]\n")


if __name__ == "__main__":
    main()