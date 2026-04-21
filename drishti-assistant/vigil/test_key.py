import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = "AIzaSyC6-7jPLKMGzvfSmcGnxmFCFCU5_-Nwa90"
genai.configure(api_key=api_key)

print(f"Testing key: {api_key[:10]}...")
try:
    model = genai.GenerativeModel('gemini-1.5-flash-8b')
    response = model.generate_content("Hello, reply with 'READY' if you can hear me.")
    print(f"Response: {response.text.strip()}")
except Exception as e:
    print(f"Error: {e}")
