import google.generativeai as genai
import os

key = (os.getenv("GEMINI_API_KEY") or "").strip()
if not key:
    raise SystemExit("Missing GEMINI_API_KEY. Set it in your environment before running this script.")
genai.configure(api_key=key)

try:
    print("Listing models...")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error: {e}")
