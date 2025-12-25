
import requests
import json
import os
import base64

# Configuration
API_KEY = "sk-UsDEOj78c99sH0F6pnYtrk576o7p2GH7qJZ6RFDco2e2G4bK"
BASE_URL = "https://api.vectorengine.ai"
MODEL = "gemini-3-pro-image-preview"

def test_native_api():
    print(f"Testing Native Gemini API on {BASE_URL}...")
    
    # Construct the native endpoint URL
    # Following the pattern in the doc: /v1beta/models/{model}:generateContent
    url = f"{BASE_URL}/v1beta/models/{MODEL}:generateContent"
    
    print(f"Endpoint: {url}")
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": "A cyberpunk street food vendor, neon lights, detailed, 8k"}
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE"], # Explicitly asking for IMAGE
            "imageConfig": {
                "aspectRatio": "9:16",
                "imageSize": "4K"
            }
        }
    }
    
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("Response received successfully!")
            data = response.json()
            print(json.dumps(data, indent=2))
            
            # Parse the response similar to how Gemini returns it
            # Usually candidates[0].content.parts[0].inline_data
            try:
                candidates = data.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    for part in parts:
                        if 'inline_data' in part:
                            mime_type = part['inline_data']['mime_type']
                            image_data = part['inline_data']['data']
                            print(f"Found image data! Mime: {mime_type}")
                            
                            # Save it
                            save_path = "test_native_9_16.png"
                            with open(save_path, "wb") as f:
                                f.write(base64.b64decode(image_data))
                            print(f"Saved image to {save_path}")
                            return True
                        elif 'text' in part:
                            print(f"Received text instead of image: {part['text']}")
                else:
                    print("No candidates in response.")
                    print(response.text)
            except Exception as e:
                print(f"Error parsing response: {e}")
                print(response.text)
        else:
            print("Request failed.")
            print(response.text)
            
    except Exception as e:
        print(f"Request exception: {e}")

if __name__ == "__main__":
    test_native_api()
