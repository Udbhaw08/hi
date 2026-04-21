import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = "AIzaSyD9t9NIrhucvO2KPNq7aLcnwwB0NBob374"
genai.configure(api_key=api_key)

try:
    models = [m.name for m in genai.list_models()]
    with open("avail_models_new.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(models))
    print(f"Listed {len(models)} models.")
except Exception as e:
    print(f"Error: {e}")
