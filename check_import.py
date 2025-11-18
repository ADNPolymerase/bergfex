import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.getcwd())

try:
    from custom_components.bergfex.parser import parse_resort_page

    print("Successfully imported custom_components.bergfex.parser")
except ModuleNotFoundError as e:
    print(f"ModuleNotFoundError: {e}")
    print(f"sys.path: {sys.path}")
    print(f"Current working directory: {os.getcwd()}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
