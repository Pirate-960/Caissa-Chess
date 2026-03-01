"""
List all Gemini models available to your Google API key, printing full model info.
Usage:
    poetry run python scripts/list_gemini_models_verbose.py
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import google.generativeai as genai
except ImportError:
    raise ImportError("google-generativeai package required. Install with: poetry add google-generativeai")

def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        print("Error: GOOGLE_API_KEY not set in .env")
        return
    genai.configure(api_key=api_key)
    print("Listing available Gemini models with full details for your API key:\n")
    try:
        models = list(genai.list_models())
        if not models:
            print("No models found. Check your API key and permissions.")
            return
        for m in models:
            print("-" * 60)
            print(f"Name: {m.name}")
            for k, v in m.__dict__.items():
                if not k.startswith("_"):
                    print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    main()
