"""
Quick bug scanner for CAISSA codebase.
Checks for common Python errors.
"""

import ast
import sys
from pathlib import Path

def check_file(filepath):
    """Check a Python file for syntax errors."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # Try to compile
        compile(code, str(filepath), 'exec')
        
        # Try to parse AST
        ast.parse(code)
        
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Error: {e}"

def main():
    """Scan all Python files in key directories."""
    print("="*60)
    print("CAISSA Bug Scanner")
    print("="*60)
    
    directories = [
        "core",
        "export",
        "aesthetic",
        "engine",
        "engines",
    ]
    
    errors = []
    checked = 0
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue
        
        for py_file in dir_path.rglob("*.py"):
            checked += 1
            success, error = check_file(py_file)
            
            if success:
                print(f"✓ {py_file}")
            else:
                print(f"✗ {py_file}")
                print(f"  {error}")
                errors.append((str(py_file), error))
    
    # Check main files
    main_files = ["main.py", "caissa.py", "config_manager.py"]
    for filename in main_files:
        filepath = Path(filename)
        if filepath.exists():
            checked += 1
            success, error = check_file(filepath)
            
            if success:
                print(f"✓ {filepath}")
            else:
                print(f"✗ {filepath}")
                print(f"  {error}")
                errors.append((filename, error))
    
    print("\n" + "="*60)
    print(f"Checked {checked} files")
    
    if errors:
        print(f"❌ Found {len(errors)} files with errors:")
        for filepath, error in errors:
            print(f"  • {filepath}: {error}")
        sys.exit(1)
    else:
        print("✅ All files passed syntax check!")
        sys.exit(0)

if __name__ == "__main__":
    main()
