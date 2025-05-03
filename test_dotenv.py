# test_dotenv.py
import os
from dotenv import load_dotenv, find_dotenv

print(f"[Test Script] Current Working Directory: {os.getcwd()}")

# Try finding it
dotenv_path = find_dotenv()
print(f"[Test Script] Path found by find_dotenv(): '{dotenv_path}'") # Add quotes for clarity

# Try loading explicitly if found
if dotenv_path:
    load_successful = load_dotenv(dotenv_path=dotenv_path, verbose=True)
    print(f"[Test Script] .env load successful (explicit path): {load_successful}")
else:
    # Try loading implicitly just in case
    print("[Test Script] Trying implicit load_dotenv()...")
    load_successful = load_dotenv(verbose=True)
    print(f"[Test Script] .env load successful (implicit): {load_successful}")


# Check the variable
loaded_key = os.getenv("GOOGLE_API_KEY")
print(f"[Test Script] Value of GOOGLE_API_KEY: '{loaded_key}'")

if loaded_key:
    print("[Test Script] SUCCESS: Key was loaded!")
else:
    print("[Test Script] FAILURE: Key was NOT loaded.")