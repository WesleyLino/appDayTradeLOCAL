import google.generativeai as genai
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ No API Key found.")
    exit(1)

genai.configure(api_key=api_key)

def test():
    print("Testing Gemini 1.5-Flash...")
    model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})
    
    prompt = "Classify sentiment of: 'The market is crashing, sell everything!'. Output JSON: { 'score': -1.0 to 1.0 }"
    
    try:
        response = model.generate_content(prompt)
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test()
