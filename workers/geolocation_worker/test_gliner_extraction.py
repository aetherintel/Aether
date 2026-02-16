import os
import sys

try:
    from gliner import GLiNER
except ImportError:
    print("GLiNER not installed. Run: pip install gliner")
    sys.exit(1)

def test_gliner():
    # Path where model is expected (adjust if running locally vs container)
    model_path = os.getenv("GLINER_MODEL_PATH", "/app/models/geolocation/gliner_model")
    
    # If running from project root locally, check logical path
    if not os.path.exists(model_path):
        local_path = "models/geolocation/gliner_model"
        if os.path.exists(local_path):
            model_path = local_path
        else:
            print(f"❌ Model not found at {model_path} or {local_path}")
            print("Please run 'python models/download_gliner.py' first.")
            return

    print(f"🚀 Loading model from {model_path}...")
    try:
        model = GLiNER.from_pretrained(model_path, local_files_only=True)
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return

    labels = ["city", "country", "location", "landmark", "address"]
    
    test_sentences = [
        "Wir treffen uns in Berlin am Alexanderplatz.",
        "Das Paket wurde nach Paris, Frankreich geschickt.",
        "Der Unfall passierte auf der A1 bei Köln.",
        "Ich bin im KaDeWe einkaufen."
    ]

    print("\n🔍 Testing Extraction:")
    for text in test_sentences:
        entities = model.predict_entities(text, labels, threshold=0.3)
        print(f"\nText: {text}")
        if not entities:
            print("  (No entities found)")
        for ent in entities:
            print(f"  - {ent['text']} ({ent['label']}) [conf: {ent['score']:.2f}]")

if __name__ == "__main__":
    test_gliner()
