"""Test script for the load metadata endpoint."""

import requests
import json

# Test the load metadata endpoint
def test_load_metadata():
    """Test loading microscopy metadata."""
    
    # Replace with actual path to your ND2 or CZI file
    test_file_path = "/path/to/your/file.nd2"
    
    url = "http://localhost:8000/api/v1/processing/load-metadata"
    
    payload = {
        "file_path": test_file_path
    }
    
    print(f"Testing load metadata endpoint...")
    print(f"File path: {test_file_path}")
    print(f"URL: {url}")
    print()
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        
        print("Response:")
        print(json.dumps(result, indent=2))
        
        if result["success"]:
            print("\n✓ Success!")
            print(f"Channels: {result['metadata']['channel_names']}")
            print(f"FOVs: {result['metadata']['n_fovs']}")
            print(f"Frames: {result['metadata']['n_frames']}")
        else:
            print(f"\n✗ Failed: {result['error']}")
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    test_load_metadata()
