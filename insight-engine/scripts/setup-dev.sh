#!/bin/bash

# Development Environment Setup Script
# This script sets up the development environment for the Insight Engine project

set -e

echo "🚀 Setting up Insight Engine development environment..."

# Check if Python 3.10+ is installed
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.10+ is required. Current version: $python_version"
    exit 1
fi

echo "✅ Python version check passed: $python_version"

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "📦 Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "✅ Poetry is already installed"
fi

# Install dependencies
echo "📦 Installing project dependencies..."
poetry install

# Install pre-commit hooks
echo "🔧 Setting up pre-commit hooks..."
poetry run pre-commit install

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please update the .env file with your configuration"
fi

# Run initial quality checks
echo "🔍 Running initial quality checks..."
poetry run ruff check src tests --fix || true
poetry run black src tests
poetry run isort src tests

# Run tests to ensure everything is working
echo "🧪 Running tests..."
poetry run pytest --tb=short

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "Available commands:"
echo "  make help          - Show all available commands"
echo "  make dev           - Start development server"
echo "  make test          - Run tests"
echo "  make quality       - Run all quality checks"
echo "  make format        - Format code"
echo ""
echo "Next steps:"
echo "1. Update .env file with your configuration"
echo "2. Start the development server: make dev"
echo "3. Start coding! 🚀"