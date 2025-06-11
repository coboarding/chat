import requests
import os

def upload_cv(file_path):
    """
    Upload a CV file to the coBoarding API
    
    Args:
        file_path (str): Path to the CV file to upload
    """
    url = "http://localhost:8000/api/cv/upload"
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return
    
    # Prepare the file for upload
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'text/markdown')}
        
        try:
            # Send POST request to upload endpoint
            print(f"Uploading {file_path}...")
            response = requests.post(url, files=files)
            
            # Check response status
            if response.status_code == 200:
                result = response.json()
                print("\nUpload successful!")
                print(f"Session ID: {result.get('session_id')}")
                print(f"Processing time: {result.get('processing_time')} seconds")
                print("\nExtracted CV data:")
                print(json.dumps(result.get('cv_data', {}), indent=2, ensure_ascii=False))
            else:
                print(f"\nError uploading file. Status code: {response.status_code}")
                print(f"Response: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"\nError making request: {e}")
        except json.JSONDecodeError:
            print("\nError: Could not parse response as JSON")
            print(f"Raw response: {response.text}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Upload a CV to the coBoarding API')
    parser.add_argument('file_path', help='Path to the CV file to upload')
    args = parser.parse_args()
    
    upload_cv(args.file_path)
