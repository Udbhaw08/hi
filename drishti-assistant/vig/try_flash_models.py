import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

with open("avail_models.txt", "r", encoding="utf-8") as f:
    models = [line.strip() for line in f if "flash" in line.lower()]

for m_name in models:
    name = m_name.replace("models/", "")
    print(f"Trying {name}...")
    try:
        model = genai.GenerativeModel(name)
        response = model.generate_content("HI")
        print(f"Success with {name}!")
        break
    except Exception as e:
        print(f"Fail with {name}: {e}")
