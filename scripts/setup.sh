#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🚀 Setting up Unattended Upgrades Slack Notifier"
echo "================================================"
echo

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.10+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Found Python $PYTHON_VERSION"

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "🔧 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "📥 Installing package in development mode..."
pip install -e .

if [ ! -f "config.ini" ]; then
    echo "📝 Creating configuration file..."
    cp config.ini.example config.ini
    echo "⚠️  Please edit config.ini with your actual Slack credentials!"
    echo "   The file has been created with placeholder values."
else
    echo "✅ Configuration file already exists"
fi

echo
echo "🎉 Setup complete!"
echo
echo "Next steps:"
echo "1. Edit config.ini with your Slack credentials"
echo "2. Test configuration: python test_config.py"
echo "3. Test the script with: python src/notifyslack.py /path/to/email.txt"
echo
echo "To activate the virtual environment in the future:"
echo "   source $VENV_DIR/bin/activate"
