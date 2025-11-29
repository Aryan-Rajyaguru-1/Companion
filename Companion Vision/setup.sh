#!/bin/bash

# Smart Glasses OCR Setup Script
# This script helps set up the development environment and build the project

echo "🤓 Smart Glasses OCR - Setup Script"
echo "====================================="

# Check if ESP-IDF is installed
if ! command -v idf.py &> /dev/null; then
    echo "❌ ESP-IDF not found in PATH"
    echo "Please install ESP-IDF and source the export script:"
    echo "  cd ~/esp/esp-idf"
    echo "  . ./export.sh"
    exit 1
fi

echo "✅ ESP-IDF found: $(idf.py --version)"

# Set target to ESP32-S3
echo "🎯 Setting target to ESP32-S3..."
idf.py set-target esp32s3

# Generate sample WAV files
echo "🎵 Generating sample WAV files..."
if command -v python3 &> /dev/null; then
    python3 generate_sample_wavs.py
elif command -v python &> /dev/null; then
    python generate_sample_wavs.py
else
    echo "⚠️  Python not found. Please install python3 and pyttsx3:"
    echo "  pip install pyttsx3"
fi

# Build the project
echo "🔨 Building project..."
idf.py build

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Build completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. 📱 Pair your Bluetooth A2DP glasses"
    echo "2. 💾 Copy WAV files from sample_wavs/ to your microSD card"
    echo "3. 🔌 Connect your XIAO ESP32S3 Sense via USB"
    echo "4. 🚀 Flash with: idf.py -p /dev/ttyUSB0 flash monitor"
    echo ""
    echo "🔧 Available VS Code tasks:"
    echo "   - ESP-IDF Build (Ctrl+Shift+P → Tasks: Run Task)"
    echo "   - ESP-IDF Flash and Monitor"
    echo "   - Generate Sample WAVs"
    echo ""
    echo "📖 See README.md for detailed setup instructions"
else
    echo "❌ Build failed. Check the error messages above."
    exit 1
fi
