#!/usr/bin/env python3
"""
Install anthropic using poetry and run tests.
"""
import os
import subprocess

# Change to project root (use current script's directory)
project_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_root)

print("=" * 60)
print("Installing anthropic package via poetry...")
print("=" * 60)

# Try poetry install first (should use lock file)
try:
    result = subprocess.run(["poetry", "install"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("STDERR:", result.stderr)
except Exception as e:
    print(f"Poetry install error: {e}")

print("\n" + "=" * 60)
print("Running pytest with all 26 tests...")
print("=" * 60 + "\n")

# Run pytest
try:
    result = subprocess.run(
        ["poetry", "run", "pytest", "tests/test_multi_providers.py", "-v", "--tb=short"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    # Print summary
    if "passed" in result.stdout:
        print("\n" + "=" * 60)
        if "26 passed" in result.stdout:
            print("✅ SUCCESS: All 26 tests PASSED!")
        elif "21 passed" in result.stdout and "5 skipped" in result.stdout:
            print("⚠️  Some tests skipped - anthropic may not be installed")
        print("=" * 60)
except Exception as e:
    print(f"Error running tests: {e}")
