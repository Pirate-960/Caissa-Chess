#!/usr/bin/env python3
"""
Simple script to install anthropic package and run tests.
"""

import subprocess
import sys

def main():
    print("Installing anthropic package...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "anthropic"])
        print("✓ anthropic package installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install anthropic: {e}")
        return 1
    
    print("\nRunning tests...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pytest",
            "tests/test_multi_providers.py", "-v"
        ])
        print("\n✓ All tests completed")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"✗ Tests failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
