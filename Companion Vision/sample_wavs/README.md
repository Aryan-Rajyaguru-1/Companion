# Sample WAV Files for Smart Glasses OCR

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
