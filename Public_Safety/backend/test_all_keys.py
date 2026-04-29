import google.generativeai as genai
import os

# Test keys loaded from environment variables only
keys_to_test = []
primary = (os.getenv("GEMINI_API_KEY") or "").strip()
if primary:
    keys_to_test.append(primary)

raw_pool = os.getenv("GEMINI_API_KEYS", "")
for key in [k.strip() for k in raw_pool.split(",") if k.strip()]:
    if key not in keys_to_test:
        keys_to_test.append(key)

if not keys_to_test:
    raise SystemExit("No Gemini keys found. Set GEMINI_API_KEY or GEMINI_API_KEYS in your environment.")

print("Testing Gemini API Keys with correct model names...\n")

for i, key in enumerate(keys_to_test, 1):
    print(f"\n{'='*60}")
    print(f"Testing Key #{i}: {key[:10]}...{key[-5:]}")
    print(f"{'='*60}")
    
    try:
        genai.configure(api_key=key)
        
        # First, list available models
        print("  [*] Listing available models...")
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        print(f"  [OK] Found {len(available_models)} models")
        
        # Find a suitable model for video
        video_model = None
        for model_name in available_models:
            if 'flash' in model_name.lower() and ('1.5' in model_name or '2.0' in model_name or '2.5' in model_name):
                video_model = model_name
                break
        
        if not video_model and available_models:
            video_model = available_models[0]
        
        if video_model:
            print(f"  [*] Testing with model: {video_model}")
            model = genai.GenerativeModel(video_model)
            response = model.generate_content("Say 'OK' if you're working")
            print(f"  [OK] Response: {response.text[:50]}")
            print(f"\n  [SUCCESS] KEY #{i} WORKS! Best model: {video_model}")
        else:
            print(f"  [WARNING] No suitable models found")
            
    except Exception as e:
        print(f"  [FAILED] KEY #{i} ERROR: {e}")

print(f"\n{'='*60}")
print("Testing complete!")
print(f"{'='*60}")
