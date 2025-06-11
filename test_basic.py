"""
Basic test script to verify the application components are working correctly.
"""
import os
import sys
from unittest.mock import MagicMock

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Mock various modules that might be missing
modules_to_mock = [
    'ollama', 
    'cv2', 
    'easyocr', 
    'pytesseract', 
    'pdf2image',
    'spacy',
    'transformers',
    'torch',
    'playwright',
    'selenium',
    'undetected_chromedriver'
]

for module_name in modules_to_mock:
    sys.modules[module_name] = MagicMock()

# Try importing key modules
try:
    import streamlit
    print("✅ Streamlit imported successfully")
except ImportError as e:
    print(f"❌ Failed to import Streamlit: {e}")

try:
    import fastapi
    print("✅ FastAPI imported successfully")
except ImportError as e:
    print(f"❌ Failed to import FastAPI: {e}")

try:
    from app.main import coBoarding
    print("✅ coBoarding class imported successfully")
    
    # Create an instance to verify basic functionality
    app = coBoarding()
    print("✅ coBoarding instance created successfully")
    
except ImportError as e:
    print(f"❌ Failed to import coBoarding class: {e}")
    print("Detailed error:")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"❌ Error creating coBoarding instance: {e}")
    print("Detailed error:")
    import traceback
    traceback.print_exc()

# Print Python path for debugging
print("\nPython path:")
for path in sys.path:
    print(f"- {path}")

print("\nTest completed.")
