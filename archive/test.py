import requests

def test_generate_trio_integration():
    url = 'http://127.0.0.1:8000/generate_trio/'

    payload = {
        'userId': 'test_user',
        'filename': 'test_cough.wav',
        'instrumentType': 'string',
        'sampleRate': 16000
    }
    
    response = requests.post(url, json=payload)
    
    print("Status code:", response.status_code)
    print("Response body:", response.text)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    assert 'pubCoughID' in data
    assert 'generated_audio_url' in data

    print("Test passed!")
    print(data)

if __name__ == "__main__":
    test_generate_trio_integration()
