import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from core.image_generator import ImageGenerator

def test():
    try:
        gen = ImageGenerator(config_path="backend/data/config.json")
        print(f"Loaded Keys: {len(gen.api_keys)} keys found.")
        print(f"Primary: {gen.api_keys[0][:8]}..." if gen.api_keys else "No keys")
        
        prompt = "A simple test image of a square"
        print("\n--- Starting Generation Test ---")
        url = gen.generate_image(prompt)
        
        if url:
            print(f"✅ Success! URL: {url}")
        else:
            print("❌ Failed (Returned None)")
            
    except Exception as e:
        print(f"🔥 CRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
