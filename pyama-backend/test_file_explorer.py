"""Test script for the file explorer API endpoints."""

import requests
import json
from pathlib import Path

# Test the file explorer endpoints
def test_file_explorer():
    """Test all file explorer endpoints."""
    
    base_url = "http://localhost:8000/api/v1/processing"
    
    print("=" * 60)
    print("PyAMA Backend File Explorer API Test")
    print("=" * 60)
    
    # Test 1: List directory contents
    print("\n1. Testing list directory endpoint...")
    test_directory = str(Path.home())  # Use home directory for testing
    
    list_payload = {
        "directory_path": test_directory,
        "include_hidden": False,
        "filter_extensions": [".nd2", ".czi", ".txt", ".py"]  # Include some common extensions
    }
    
    try:
        response = requests.post(f"{base_url}/list-directory", json=list_payload)
        response.raise_for_status()
        result = response.json()
        
        if result["success"]:
            print(f"✓ Successfully listed directory: {result['directory_path']}")
            print(f"  Found {len(result['items'])} items")
            
            # Show first few items
            for i, item in enumerate(result['items'][:5]):
                item_type = "DIR" if item['is_directory'] else "FILE"
                size_str = f" ({item['size_bytes']} bytes)" if item['size_bytes'] else ""
                print(f"  {item_type}: {item['name']}{size_str}")
            
            if len(result['items']) > 5:
                print(f"  ... and {len(result['items']) - 5} more items")
        else:
            print(f"✗ Failed: {result['error']}")
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 2: Search for microscopy files
    print("\n2. Testing search files endpoint...")
    
    search_payload = {
        "search_path": test_directory,
        "pattern": "**/*.{nd2,czi}",
        "max_depth": 3,
        "include_hidden": False
    }
    
    try:
        response = requests.post(f"{base_url}/search-files", json=search_payload)
        response.raise_for_status()
        result = response.json()
        
        if result["success"]:
            print(f"✓ Successfully searched directory: {result['search_path']}")
            print(f"  Found {result['total_found']} microscopy files")
            
            # Show found files
            for file_item in result['files'][:5]:
                size_str = f" ({file_item['size_bytes']} bytes)" if file_item['size_bytes'] else ""
                print(f"  FILE: {file_item['name']}{size_str}")
            
            if len(result['files']) > 5:
                print(f"  ... and {len(result['files']) - 5} more files")
        else:
            print(f"✗ Failed: {result['error']}")
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 3: Get file information
    print("\n3. Testing file info endpoint...")
    
    # Try to find a test file (look for any .py file in the current directory)
    test_file = None
    current_dir = Path.cwd()
    for py_file in current_dir.glob("*.py"):
        test_file = str(py_file)
        break
    
    if test_file:
        file_info_payload = {
            "file_path": test_file
        }
        
        try:
            response = requests.post(f"{base_url}/file-info", json=file_info_payload)
            response.raise_for_status()
            result = response.json()
            
            if result["success"]:
                print(f"✓ Successfully got file info for: {test_file}")
                file_info = result['file_info']
                print(f"  Name: {file_info['name']}")
                print(f"  Size: {file_info['size_bytes']} bytes")
                print(f"  Extension: {file_info['extension']}")
                print(f"  Is microscopy file: {result['is_microscopy_file']}")
                
                if result['metadata_preview']:
                    metadata = result['metadata_preview']
                    print(f"  Metadata preview:")
                    print(f"    Channels: {metadata['n_channels']}")
                    print(f"    FOVs: {metadata['n_fovs']}")
                    print(f"    Frames: {metadata['n_frames']}")
            else:
                print(f"✗ Failed: {result['error']}")
                
        except requests.exceptions.RequestException as e:
            print(f"✗ Request failed: {e}")
        except Exception as e:
            print(f"✗ Error: {e}")
    else:
        print("  No test file found to check file info")
    
    # Test 4: Get recent files
    print("\n4. Testing recent files endpoint...")
    
    try:
        response = requests.get(f"{base_url}/recent-files?limit=5&extensions=.nd2,.czi")
        response.raise_for_status()
        result = response.json()
        
        if result["success"]:
            print(f"✓ Successfully got recent files")
            print(f"  Message: {result['message']}")
            print(f"  Recent files: {len(result['recent_files'])}")
        else:
            print(f"✗ Failed: {result.get('error', 'Unknown error')}")
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("File Explorer API Test Complete")
    print("=" * 60)


def test_with_nd2_file():
    """Test with an actual ND2 file if available."""
    
    print("\n" + "=" * 60)
    print("Testing with ND2 file (if available)")
    print("=" * 60)
    
    # Look for ND2 files in common locations
    search_paths = [
        Path.home() / "Downloads",
        Path.home() / "Documents",
        Path.home() / "Desktop",
        Path.cwd(),
    ]
    
    nd2_files = []
    for search_path in search_paths:
        if search_path.exists():
            nd2_files.extend(list(search_path.glob("**/*.nd2")))
            if len(nd2_files) >= 3:  # Limit to first 3 files
                break
    
    if not nd2_files:
        print("No ND2 files found in common locations.")
        print("To test with actual ND2 files, place them in Downloads, Documents, or Desktop.")
        return
    
    print(f"Found {len(nd2_files)} ND2 files:")
    for i, nd2_file in enumerate(nd2_files[:3]):
        print(f"  {i+1}. {nd2_file}")
    
    # Test file info with the first ND2 file
    test_file = str(nd2_files[0])
    print(f"\nTesting file info with: {test_file}")
    
    base_url = "http://localhost:8000/api/v1/processing"
    file_info_payload = {
        "file_path": test_file
    }
    
    try:
        response = requests.post(f"{base_url}/file-info", json=file_info_payload)
        response.raise_for_status()
        result = response.json()
        
        if result["success"]:
            print(f"✓ Successfully got file info for ND2 file")
            file_info = result['file_info']
            print(f"  Name: {file_info['name']}")
            print(f"  Size: {file_info['size_bytes']} bytes")
            print(f"  Is microscopy file: {result['is_microscopy_file']}")
            
            if result['metadata_preview']:
                metadata = result['metadata_preview']
                print(f"  Metadata preview:")
                print(f"    File type: {metadata['file_type']}")
                print(f"    Dimensions: {metadata['width']}x{metadata['height']}")
                print(f"    Channels: {metadata['n_channels']} ({', '.join(metadata['channel_names'])})")
                print(f"    FOVs: {metadata['n_fovs']}")
                print(f"    Frames: {metadata['n_frames']}")
                print(f"    Data type: {metadata['dtype']}")
        else:
            print(f"✗ Failed: {result['error']}")
            
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    print("Make sure the PyAMA Backend server is running:")
    print("  cd pyama-backend")
    print("  uv run python -m pyama_backend")
    print()
    
    # Test basic file explorer functionality
    test_file_explorer()
    
    # Test with actual ND2 files if available
    test_with_nd2_file()