"""
Basic test script to verify the application components are working correctly.
"""
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

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
except ImportError as e:
    print(f"❌ Failed to import coBoarding class: {e}")
    print("Detailed error:")
    import traceback
    traceback.print_exc()

# Print Python path for debugging
print("\nPython path:")
for path in sys.path:
    print(f"- {path}")

print("\nTest completed.")
