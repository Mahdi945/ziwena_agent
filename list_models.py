"""
Run this once to see exactly which models YOUR API key can access.
python list_models.py
"""
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("Models available to your key:\n")
for m in client.models.list():
    print(m.name)
