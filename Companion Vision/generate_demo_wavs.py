#!/usr/bin/env python3
"""
Generate additional WAV files for demo OCR patterns
"""

import os
import numpy as np
from scipy.io.wavfile import write
import pyttsx3

# Audio settings
SAMPLE_RATE = 16000
DURATION = 2.0  # seconds

def generate_tts_audio(text, filename, language='en'):
    """Generate TTS audio and save as WAV file"""
    try:
        engine = pyttsx3.init()
        
        # Set properties for embedded device compatibility
        engine.setProperty('rate', 150)  # Slower speech rate
        engine.setProperty('volume', 0.9)
        
        # Set voice based on language
        voices = engine.getProperty('voices')
        if language == 'hi' and len(voices) > 1:
            # Try to find Hindi voice
            for voice in voices:
                if 'hindi' in voice.name.lower() or 'hi' in voice.id.lower():
                    engine.setProperty('voice', voice.id)
                    break
        
        # Save to temporary WAV file
        temp_file = filename.replace('.wav', '_temp.wav')
        engine.save_to_file(text, temp_file)
        engine.runAndWait()
        
        # Convert to proper format if needed
        if os.path.exists(temp_file):
            os.rename(temp_file, filename)
            print(f"Audio saved to {filename}")
        else:
            # Fallback: generate simple tone
            generate_simple_tone(filename, text)
            
    except Exception as e:
        print(f"TTS failed for {text}: {e}")
        # Fallback: generate simple tone
        generate_simple_tone(filename, text)

def generate_simple_tone(filename, text):
    """Generate a simple tone as fallback"""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), False)
    # Generate different frequencies based on text length
    freq = 440 + (len(text) * 20)  # Vary frequency based on text
    audio = 0.3 * np.sin(2 * np.pi * freq * t)
    
    # Add some variation
    audio *= np.exp(-t / 1.0)  # Fade out
    
    # Convert to 16-bit PCM
    audio_int16 = (audio * 32767).astype(np.int16)
    write(filename, SAMPLE_RATE, audio_int16)
    print(f"Tone generated for {text} -> {filename}")

def main():
    print("Generating demo OCR pattern WAV files...")
    
    # Create directory if it doesn't exist
    os.makedirs('sample_wavs', exist_ok=True)
    
    # Demo patterns from ocr_processor.c
    demo_patterns = [
        # English patterns - using exact case from OCR
        ("STOP", "english_STOP.wav", "Stop sign ahead", "en"),
        ("EXIT", "english_EXIT.wav", "Exit here", "en"),  
        ("ENTRANCE", "english_ENTRANCE.wav", "Entrance ahead", "en"),
        ("BUS", "english_BUS.wav", "Bus stop", "en"),
        ("STATION", "english_STATION.wav", "Station ahead", "en"),
        
        # Hindi patterns (in Devanagari)
        ("रुकें", "hindi_रुकें.wav", "रुकना", "hi"),  # Stop
        ("प्रवेश", "hindi_प्रवेश.wav", "प्रवेश द्वार", "hi"),  # Entrance
        ("निकास", "hindi_निकास.wav", "निकास", "hi"),  # Exit  
        ("बस", "hindi_बस.wav", "बस स्टॉप", "hi"),  # Bus
        ("स्टेशन", "hindi_स्टेशन.wav", "स्टेशन", "hi"),  # Station
        
        # Gujarati patterns (basic English pronunciation for now)
        ("અટકો", "gujarati_અટકો.wav", "Stop", "en"),  # Stop
        ("પ્રવેશ", "gujarati_પ્રવેશ.wav", "Entrance", "en"),  # Entrance
        ("બસ", "gujarati_બસ.wav", "Bus", "en"),  # Bus
        ("સ્ટેશન", "gujarati_સ્ટેશન.wav", "Station", "en"),  # Station
    ]
    
    # Also create notification.wav as fallback
    demo_patterns.append(("notification", "notification.wav", "Text detected", "en"))
    
    for pattern_text, filename, speech_text, lang in demo_patterns:
        filepath = os.path.join('sample_wavs', filename)
        print(f"  Creating: {filepath} - '{speech_text}'")
        generate_tts_audio(speech_text, filepath, lang)
    
    print("\nDemo OCR pattern WAV files generated!")
    print("Copy these files to your SD card:")
    print("1. Insert microSD card into your computer")
    print("2. Copy all files from 'sample_wavs/' to the SD card root")
    print("3. Insert SD card into XIAO ESP32S3 Sense")
    print("4. Reset the device to test audio feedback")

if __name__ == "__main__":
    main()
