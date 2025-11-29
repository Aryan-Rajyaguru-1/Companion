#!/usr/bin/env python3
"""
Sample WAV file generator for Smart Glasses OCR system
Generates demo WAV files with Text-to-Speech for testing

Requirements:
    pip install pyttsx3 numpy scipy

Usage:
    python generate_sample_wavs.py
"""

import pyttsx3
import os
import sys

def generate_wav_files():
    """Generate sample WAV files for different languages and phrases"""
    
    # Initialize TTS engine
    engine = pyttsx3.init()
    
    # Set properties
    engine.setProperty('rate', 150)    # Speed of speech
    engine.setProperty('volume', 0.9)  # Volume level (0.0 to 1.0)
    
    # Get available voices
    voices = engine.getProperty('voices')
    
    # Sample phrases for different scenarios
    phrases = {
        'english': [
            ('notification', 'Text detected'),
            ('stop', 'Stop sign ahead'),
            ('bus', 'Bus approaching'),
            ('entrance', 'Entrance on your left'),
            ('exit', 'Exit on your right'),
            ('station', 'Bus station ahead'),
            ('direction_left', 'Turn left'),
            ('direction_right', 'Turn right'),
            ('direction_straight', 'Continue straight'),
            ('steps_10', 'Ten steps ahead'),
            ('steps_20', 'Twenty steps ahead'),
            ('warning', 'Obstacle detected'),
        ],
        'hindi': [
            ('notification', 'टेक्स्ट मिला'),  # Text found
            ('stop', 'रुकने का संकेत'),        # Stop sign
            ('bus', 'बस आ रही है'),          # Bus coming
            ('entrance', 'बाईं ओर प्रवेश'),    # Entrance on left
            ('exit', 'दाईं ओर निकास'),       # Exit on right
            ('station', 'बस स्टेशन सामने'),   # Bus station ahead
            ('direction_left', 'बाएं मुड़ें'),   # Turn left
            ('direction_right', 'दाएं मुड़ें'),  # Turn right
            ('steps_10', 'दस कदम आगे'),       # Ten steps ahead
            ('warning', 'बाधा है'),           # Obstacle
        ]
    }
    
    output_dir = "sample_wavs"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print("Generating sample WAV files...")
    
    for language, phrase_list in phrases.items():
        print(f"\nGenerating {language} phrases:")
        
        # Set voice for language (this is basic - real implementation would use proper language models)
        if language == 'english':
            # Find English voice
            for voice in voices:
                if 'english' in voice.name.lower() or 'en' in voice.id.lower():
                    engine.setProperty('voice', voice.id)
                    break
        
        for phrase_id, text in phrase_list:
            filename = f"{output_dir}/{language}_{phrase_id}.wav"
            print(f"  Creating: {filename} - '{text}'")
            
            try:
                engine.save_to_file(text, filename)
                engine.runAndWait()
            except Exception as e:
                print(f"    Error creating {filename}: {e}")
    
    print(f"\nSample WAV files generated in '{output_dir}' directory")
    print("Copy these files to your SD card in the /sdcard/ directory on the ESP32")

def create_readme():
    """Create a README file explaining the WAV files"""
    readme_content = """# Sample WAV Files for Smart Glasses OCR

This directory contains sample WAV files for testing the smart glasses OCR system.

## File Naming Convention
- `{language}_{phrase_id}.wav`
- Languages: english, hindi, gujarati
- Example: `english_notification.wav`, `hindi_stop.wav`

## Usage
1. Copy all WAV files to the microSD card
2. Insert SD card into the XIAO ESP32S3 Sense
3. The system will automatically play appropriate files based on OCR results

## Audio Specifications
- Format: WAV (PCM)
- Sample Rate: 44.1 kHz (recommended for A2DP)
- Bit Depth: 16-bit
- Channels: Mono or Stereo

## Customization
To add your own phrases:
1. Record or generate WAV files with the above specifications
2. Name them according to the convention
3. Update the OCR processor to map recognized text to your filenames

## File List
- notification.wav - General notification sound
- stop.wav - Stop sign detected
- bus.wav - Bus detected
- entrance.wav - Entrance detected
- exit.wav - Exit detected
- station.wav - Bus station detected
- direction_left.wav - Turn left instruction
- direction_right.wav - Turn right instruction
- direction_straight.wav - Continue straight
- steps_10.wav - Ten steps ahead
- steps_20.wav - Twenty steps ahead
- warning.wav - General warning/obstacle
"""
    
    with open("sample_wavs/README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print("Created README.md in sample_wavs directory")

if __name__ == "__main__":
    try:
        generate_wav_files()
        create_readme()
        print("\nDone! Remember to:")
        print("1. Copy WAV files to your microSD card")
        print("2. Insert SD card into XIAO ESP32S3 Sense")
        print("3. Pair your Bluetooth glasses with the device")
    except ImportError as e:
        print(f"Error: Missing required package. Please install: pip install pyttsx3")
        print(f"Details: {e}")
    except Exception as e:
        print(f"Error generating WAV files: {e}")
