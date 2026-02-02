#!/usr/bin/env python3
"""
Check if anthropic is installed and attempt to import it.
"""

import sys
import importlib.util

print("=" * 60)
print("Python Environment Check")
print("=" * 60)
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Python path: {sys.path[:3]}")

print("\n" + "=" * 60)
print("Checking installed packages...")
print("=" * 60)

packages_to_check = [
    'anthropic',
    'openai',
    'google.generativeai',
    'azure.openai',
    'requests',
    'tenacity',
    'pytest'
]

for pkg in packages_to_check:
    spec = importlib.util.find_spec(pkg)
    status = "✓ INSTALLED" if spec is not None else "✗ NOT FOUND"
    print(f"{pkg:25} {status}")

print("\n" + "=" * 60)
print("Attempting to import test module...")
print("=" * 60)

try:
    # Add project to path
    sys.path.insert(0, r"d:\Github Projects\Games\Chess\caissa-chess")
    
    from tests.test_multi_providers import (
        TestAnthropicProvider,
        TestAzureOpenAIProvider,
        TestGoogleGeminiProvider,
        TestOllamaProvider,
        TestProviderIntegration
    )
    print("✓ Test module imported successfully")
    
    # Count test methods
    anthropic_tests = [m for m in dir(TestAnthropicProvider) if m.startswith('test_')]
    azure_tests = [m for m in dir(TestAzureOpenAIProvider) if m.startswith('test_')]
    google_tests = [m for m in dir(TestGoogleGeminiProvider) if m.startswith('test_')]
    ollama_tests = [m for m in dir(TestOllamaProvider) if m.startswith('test_')]
    integration_tests = [m for m in dir(TestProviderIntegration) if m.startswith('test_')]
    
    total = len(anthropic_tests) + len(azure_tests) + len(google_tests) + len(ollama_tests) + len(integration_tests)
    
    print(f"\nTest counts:")
    print(f"  Anthropic:    {len(anthropic_tests)} tests")
    print(f"  Azure:        {len(azure_tests)} tests")
    print(f"  Google:       {len(google_tests)} tests")
    print(f"  Ollama:       {len(ollama_tests)} tests")
    print(f"  Integration:  {len(integration_tests)} tests")
    print(f"  TOTAL:        {total} tests")
    
except Exception as e:
    print(f"✗ Failed to import test module: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Installation Status: Check if anthropic is marked ✓ above")
print("=" * 60)
