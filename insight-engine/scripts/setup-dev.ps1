# Development Environment Setup Script for Windows
# This script sets up the development environment for the Insight Engine project

$ErrorActionPreference = "Stop"

Write-Host "🚀 Setting up Insight Engine development environment..." -ForegroundColor Green

# Check if Python 3.10+ is installed
try {
    $pythonVersion = python --version 2>&1 | Select-String -Pattern '\d+\.\d+' | ForEach-Object { $_.Matches[0].Value }
    $requiredVersion = [Version]"3.10"
    $currentVersion = [Version]$pythonVersion
    
    if ($currentVersion -lt $requiredVersion) {
        Write-Host "❌ Python 3.10+ is required. Current version: $pythonVersion" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✅ Python version check passed: $pythonVersion" -ForegroundColor Green
}
catch {
    Write-Host "❌ Python is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Check if Poetry is installed
try {
    poetry --version | Out-Null
    Write-Host "✅ Poetry is already installed" -ForegroundColor Green
}
catch {
    Write-Host "📦 Installing Poetry..." -ForegroundColor Yellow
    (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
    $env:PATH += ";$env:APPDATA\Python\Scripts"
}

# Navigate to project directory
Set-Location insight-engine

# Install dependencies
Write-Host "📦 Installing project dependencies..." -ForegroundColor Yellow
poetry install

# Install pre-commit hooks
Write-Host "🔧 Setting up pre-commit hooks..." -ForegroundColor Yellow
poetry run pre-commit install

# Create .env file if it doesn't exist
if (-not (Test-Path .env)) {
    Write-Host "📝 Creating .env file from template..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "⚠️  Please update the .env file with your configuration" -ForegroundColor Yellow
}

# Run initial quality checks
Write-Host "🔍 Running initial quality checks..." -ForegroundColor Yellow
try {
    poetry run ruff check src tests --fix
} catch {
    Write-Host "Ruff check completed with warnings" -ForegroundColor Yellow
}

poetry run black src tests
poetry run isort src tests

# Run tests to ensure everything is working
Write-Host "🧪 Running tests..." -ForegroundColor Yellow
poetry run pytest --tb=short

Write-Host ""
Write-Host "🎉 Development environment setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Available commands:" -ForegroundColor Cyan
Write-Host "  make help          - Show all available commands"
Write-Host "  make dev           - Start development server"
Write-Host "  make test          - Run tests"
Write-Host "  make quality       - Run all quality checks"
Write-Host "  make format        - Format code"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Update .env file with your configuration"
Write-Host "2. Start the development server: make dev"
Write-Host "3. Start coding! 🚀"