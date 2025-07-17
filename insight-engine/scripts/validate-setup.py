#!/usr/bin/env python3
"""
Development Environment Validation Script

This script validates that the development environment is properly set up
and all required tools are working correctly.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def run_command(cmd: List[str]) -> Tuple[bool, str]:
    """Run a command and return success status and output."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"


def check_python_version() -> bool:
    """Check if Python version is 3.10 or higher."""
    print("🐍 Checking Python version...")
    success, output = run_command([sys.executable, "--version"])
    if success:
        version_str = output.split()[1]
        major, minor = map(int, version_str.split(".")[:2])
        if major >= 3 and minor >= 10:
            print(f"✅ Python {version_str} - OK")
            return True
        else:
            print(f"❌ Python {version_str} - Need 3.10+")
            return False
    else:
        print(f"❌ Failed to check Python version: {output}")
        return False


def check_poetry() -> bool:
    """Check if Poetry is installed and working."""
    print("📦 Checking Poetry...")
    success, output = run_command(["poetry", "--version"])
    if success:
        print(f"✅ {output} - OK")
        return True
    else:
        print(f"❌ Poetry not found: {output}")
        return False


def check_dependencies() -> bool:
    """Check if project dependencies are installed."""
    print("📚 Checking project dependencies...")
    success, output = run_command(["poetry", "check"])
    if success:
        print("✅ Dependencies - OK")
        return True
    else:
        print(f"❌ Dependencies issue: {output}")
        return False


def check_code_quality_tools() -> bool:
    """Check if code quality tools are working."""
    tools = [
        ("black", ["poetry", "run", "black", "--version"]),
        ("isort", ["poetry", "run", "isort", "--version"]),
        ("ruff", ["poetry", "run", "ruff", "--version"]),
        ("mypy", ["poetry", "run", "mypy", "--version"]),
        ("pytest", ["poetry", "run", "pytest", "--version"]),
    ]
    
    all_good = True
    print("🔧 Checking code quality tools...")
    
    for tool_name, cmd in tools:
        success, output = run_command(cmd)
        if success:
            version = output.split('\n')[0]  # Get first line
            print(f"✅ {tool_name}: {version}")
        else:
            print(f"❌ {tool_name}: {output}")
            all_good = False
    
    return all_good


def check_pre_commit() -> bool:
    """Check if pre-commit is installed."""
    print("🪝 Checking pre-commit hooks...")
    
    # Check if pre-commit is installed
    success, output = run_command(["poetry", "run", "pre-commit", "--version"])
    if not success:
        print(f"❌ pre-commit not found: {output}")
        return False
    
    print(f"✅ {output}")
    
    # Check if hooks are installed
    git_hooks_dir = Path(".git/hooks")
    if git_hooks_dir.exists() and (git_hooks_dir / "pre-commit").exists():
        print("✅ Pre-commit hooks installed")
        return True
    else:
        print("⚠️  Pre-commit hooks not installed. Run: poetry run pre-commit install")
        return False


def check_env_file() -> bool:
    """Check if .env file exists."""
    print("🔧 Checking environment configuration...")
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print("✅ .env file exists")
        return True
    elif env_example.exists():
        print("⚠️  .env file missing. Copy from .env.example")
        return False
    else:
        print("❌ No .env or .env.example file found")
        return False


def run_basic_tests() -> bool:
    """Run a basic test to ensure the setup works."""
    print("🧪 Running basic validation tests...")
    success, output = run_command([
        "poetry", "run", "python", "-c", 
        "import fastapi, pydantic, langchain; print('Core imports successful')"
    ])
    
    if success:
        print("✅ Core imports working")
        return True
    else:
        print(f"❌ Import test failed: {output}")
        return False


def main():
    """Main validation function."""
    print("🚀 Validating Insight Engine development environment...\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("Poetry", check_poetry),
        ("Dependencies", check_dependencies),
        ("Code Quality Tools", check_code_quality_tools),
        ("Pre-commit", check_pre_commit),
        ("Environment File", check_env_file),
        ("Basic Tests", run_basic_tests),
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} failed with error: {e}")
            results.append((check_name, False))
        print()  # Add spacing between checks
    
    # Summary
    print("=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {check_name}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All checks passed! Your development environment is ready.")
        print("\nNext steps:")
        print("1. Start the development server: make dev")
        print("2. Start the worker: make worker")
        print("3. Run tests: make test")
        return True
    else:
        print(f"\n⚠️  {total - passed} checks failed. Please fix the issues above.")
        print("\nFor help, see DEVELOPMENT.md or run: make help")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)