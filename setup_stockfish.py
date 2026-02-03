#!/usr/bin/env python3
"""
setup_stockfish.py

Setup and configuration helper for Stockfish chess engine.

Features:
- Detect if Stockfish is already installed
- Download appropriate binary for current system
- Add Stockfish path to .env configuration
- Validate installation

Usage:
    python setup_stockfish.py
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path


def check_stockfish() -> str | None:
    """
    Check if Stockfish is already installed in system PATH.
    
    Returns:
        Path to stockfish executable if found, None otherwise
    """
    path = shutil.which("stockfish")
    if path:
        print(f"✅ Stockfish found: {path}")
        # Try to get version
        try:
            result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=2)
            if result.stdout:
                print(f"   Version: {result.stdout.strip()}")
        except Exception:
            pass
        return path
    print("❌ Stockfish not found in PATH")
    return None


def get_download_url() -> str:
    """
    Get appropriate Stockfish download URL for current system.
    
    Returns:
        Download URL for the latest Stockfish release
    
    Raises:
        ValueError: If platform is not supported
    """
    system = platform.system()
    arch = platform.machine()
    
    base_url = "https://github.com/official-stockfish/Stockfish/releases/download/sf16"
    
    if system == "Windows":
        return f"{base_url}/stockfish-windows-x86_64-avx2.exe"
    elif system == "Darwin":  # macOS
        if arch == "arm64":
            return f"{base_url}/stockfish-macos-m1-apple-silicon"
        else:
            return f"{base_url}/stockfish-macos-x86-64"
    elif system == "Linux":
        return f"{base_url}/stockfish-ubuntu-x86_64-avx2"
    else:
        raise ValueError(f"Unsupported platform: {system} ({arch})")


def download_stockfish(url: str, destination: Path) -> bool:
    """
    Download Stockfish binary from official release.
    
    Args:
        url: Download URL
        destination: Where to save the binary
    
    Returns:
        True if successful, False otherwise
    """
    print(f"📥 Downloading Stockfish from: {url}")
    
    try:
        import urllib.request
        urllib.request.urlretrieve(url, destination)
        
        # Make executable on Unix
        if platform.system() != "Windows":
            os.chmod(destination, 0o755)
        
        print(f"✅ Downloaded to: {destination}")
        return True
    
    except ImportError:
        # Try using curl if urllib not available
        print("⚠️  Using curl to download...")
        try:
            result = subprocess.run(
                ["curl", "-L", "-o", str(destination), url],
                check=True
            )
            if platform.system() != "Windows":
                os.chmod(destination, 0o755)
            print(f"✅ Downloaded to: {destination}")
            return True
        except Exception as e:
            print(f"❌ Download failed: {str(e)}")
            return False
    
    except Exception as e:
        print(f"❌ Download failed: {str(e)}")
        return False


def add_to_path_env(binary_path: str) -> bool:
    """
    Add Stockfish to system PATH (platform-specific).
    
    Args:
        binary_path: Path to stockfish executable
    
    Returns:
        True if successful
    """
    try:
        system = platform.system()
        
        if system == "Windows":
            # Add to PATH via environment variable (current session only)
            os.environ["PATH"] = f"{os.path.dirname(binary_path)};{os.environ.get('PATH', '')}"
            print(f"✅ Added to PATH (current session)")
            return True
        else:
            # On Unix, create symlink to /usr/local/bin if writable
            try:
                link_path = "/usr/local/bin/stockfish"
                if not os.path.exists(link_path):
                    os.symlink(binary_path, link_path)
                    print(f"✅ Created symlink: {link_path}")
                return True
            except PermissionError:
                print(f"⚠️  Need sudo to create symlink. Please run:")
                print(f"   sudo ln -s {binary_path} /usr/local/bin/stockfish")
                return False
    
    except Exception as e:
        print(f"❌ Failed to add to PATH: {str(e)}")
        return False


def setup_env() -> None:
    """Configure .env file with Stockfish path."""
    env_file = Path(".env")
    stockfish_path = shutil.which("stockfish")
    
    if not stockfish_path:
        print("⚠️  Stockfish path not found. Skipping .env setup.")
        return
    
    env_line = f"STOCKFISH_PATH={stockfish_path}\n"
    
    # Check if .env exists and already has the variable
    if env_file.exists():
        with open(env_file, "r") as f:
            content = f.read()
        
        if "STOCKFISH_PATH=" in content:
            print("⚠️  STOCKFISH_PATH already in .env")
            return
        
        # Append to existing .env
        with open(env_file, "a") as f:
            f.write(env_line)
    else:
        # Create new .env
        with open(env_file, "w") as f:
            f.write(env_line)
    
    print(f"✅ Added to .env: {env_line.strip()}")


def print_install_instructions():
    """Print installation instructions for different platforms."""
    system = platform.system()
    
    print("\n📖 Manual Installation Instructions:")
    print("=" * 60)
    
    if system == "Windows":
        print("Windows (via Chocolatey):")
        print("  choco install stockfish")
        print("\nOr download manually:")
        print("  https://stockfishchess.org/download/")
    
    elif system == "Darwin":
        print("macOS (via Homebrew):")
        print("  brew install stockfish")
    
    elif system == "Linux":
        print("Linux:")
        print("  Ubuntu/Debian: sudo apt-get install stockfish")
        print("  Fedora: sudo dnf install stockfish")
        print("  Arch: sudo pacman -S stockfish")
    
    print("\nAfter installation, run this script again.")
    print("=" * 60 + "\n")


def validate_installation() -> bool:
    """
    Validate that Stockfish is properly installed and functional.
    
    Returns:
        True if valid, False otherwise
    """
    path = shutil.which("stockfish")
    if not path:
        print("❌ Stockfish not found in PATH")
        return False
    
    try:
        # Try to run stockfish and check for UCI protocol
        result = subprocess.run(
            [path],
            input="uci\nquit\n",
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if "uciok" in result.stdout:
            print(f"✅ Stockfish is functional: {path}")
            return True
        else:
            print(f"❌ Stockfish at {path} doesn't respond to UCI")
            return False
    
    except subprocess.TimeoutExpired:
        print(f"❌ Stockfish at {path} timed out")
        return False
    except Exception as e:
        print(f"❌ Failed to validate Stockfish: {str(e)}")
        return False


def main():
    """Main setup routine."""
    print("\n" + "=" * 60)
    print("⚙️  CAISSA Stockfish Setup")
    print("=" * 60 + "\n")
    
    # Check if already installed
    if check_stockfish():
        setup_env()
        if validate_installation():
            print("\n✅ Setup complete! Stockfish is ready for use.")
            return 0
        else:
            return 1
    
    # Suggest installation methods
    print("\n📖 Installation Options:")
    print("  1. Download binary automatically (this script)")
    print("  2. Manual installation (see instructions below)")
    print("  3. Package manager (apt, brew, choco)")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == "1":
        try:
            url = get_download_url()
            print(f"\n📋 Platform: {platform.system()} ({platform.machine()})")
            
            # Download to current directory or standard location
            if platform.system() == "Windows":
                dest = Path("./stockfish.exe")
            else:
                dest = Path("./stockfish")
            
            if download_stockfish(url, dest):
                add_to_path_env(str(dest))
                setup_env()
                
                if validate_installation():
                    print("\n✅ Setup complete! Stockfish is ready for use.")
                    return 0
                else:
                    print("\n⚠️  Downloaded but validation failed")
                    return 1
            else:
                return 1
        
        except ValueError as e:
            print(f"\n❌ Error: {str(e)}")
            print_install_instructions()
            return 1
    
    elif choice == "2":
        print_install_instructions()
        return 0
    
    elif choice == "3":
        print_install_instructions()
        return 0
    
    else:
        print("❌ Invalid choice")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
