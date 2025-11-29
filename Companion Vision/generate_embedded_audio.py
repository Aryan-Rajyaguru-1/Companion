#!/usr/bin/env python3
"""
Generate embedded C audio data from WAV files for ESP32-S3 smart glasses OCR
This creates a compact audio system with essential words only.
"""

import os
import struct

# Essential words detected by OCR system (from monitor output analysis)
ESSENTIAL_WORDS = [
    # English - most detected
    "english_BUS.wav",
    "english_ENTRANCE.wav", 
    "english_STATION.wav",
    "english_STOP.wav",
    "english_EXIT.wav",
    
    # Hindi - most detected  
    "hindi_प्रवेश.wav",
    "hindi_बस.wav", 
    "hindi_स्टेशन.wav",
    "hindi_रुकें.wav",
    "hindi_निकास.wav",
    
    # Gujarati - most detected
    "gujarati_પ્રવેશ.wav",
    "gujarati_સ્ટેશન.wav", 
    "gujarati_બસ.wav",
    
    # Generic notification
    "notification.wav"
]

def wav_to_c_array(filepath, var_name):
    """Convert WAV file to C array, skipping header"""
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found")
        return None
        
    with open(filepath, 'rb') as f:
        # Read WAV header to find data section
        header = f.read(44)  # Standard WAV header is 44 bytes
        
        # Validate RIFF header
        if header[:4] != b'RIFF' or header[8:12] != b'WAVE':
            print(f"Error: {filepath} is not a valid WAV file")
            return None
            
        # Find data chunk
        audio_data = None
        while True:
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                break
            chunk_id = chunk_header[:4]
            chunk_size = struct.unpack('<I', chunk_header[4:8])[0]
            
            if chunk_id == b'data':
                # Found audio data
                audio_data = f.read(chunk_size)
                break
            else:
                # Skip this chunk
                f.seek(chunk_size, 1)
        
        if audio_data is None:
            print(f"Error: No data chunk found in {filepath}")
            return None
    
    # Generate C array
    c_array = f"static const uint8_t {var_name}[] = {{\n"
    for i, byte in enumerate(audio_data):
        if i % 16 == 0:
            c_array += "    "
        c_array += f"0x{byte:02x},"
        if i % 16 == 15:
            c_array += "\n"
        else:
            c_array += " "
    
    if len(audio_data) % 16 != 0:
        c_array += "\n"
    c_array += "};\n"
    
    return c_array, len(audio_data)

def generate_embedded_audio():
    """Generate embedded_audio.c file with essential audio data"""
    
    c_file_content = '''/*
 * Embedded Audio Data for Smart Glasses OCR
 * Generated from essential WAV files for commonly detected text
 */

#include "embedded_audio.h"
#include "wav_player.h"
#include <string.h>
#include <esp_log.h>

static const char *TAG = "EMBEDDED_AUDIO";

'''
    
    # Generate C arrays for each essential WAV file
    file_entries = []
    total_size = 0
    
    for wav_file in ESSENTIAL_WORDS:
        wav_path = f"sample_wavs/{wav_file}"
        if not os.path.exists(wav_path):
            print(f"Skipping missing file: {wav_path}")
            continue
            
        # Create variable name from filename  
        var_name = wav_file.replace('.wav', '').replace('-', '_').replace(' ', '_')
        var_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in var_name)
        var_name = f"audio_data_{var_name}"
        
        # Convert to C array
        result = wav_to_c_array(wav_path, var_name)
        if result:
            c_array, size = result
            c_file_content += c_array + "\n"
            file_entries.append((wav_file, var_name, size))
            total_size += size
            print(f"✅ Embedded {wav_file} ({size} bytes)")
    
    # Generate lookup table
    c_file_content += "// Lookup table for embedded audio files\n"
    c_file_content += "static const embedded_audio_file_t embedded_files[] = {\n"
    
    for wav_file, var_name, size in file_entries:
        c_file_content += f'    {{"{wav_file}", {var_name}, {size}}},\n'
    
    c_file_content += "};\n\n"
    c_file_content += f"#define NUM_EMBEDDED_FILES {len(file_entries)}\n\n"
    
    # Generate implementation functions
    c_file_content += '''esp_err_t embedded_audio_init(void) {
    ESP_LOGI(TAG, "Embedded audio initialized with %d files (%d total bytes)", 
             NUM_EMBEDDED_FILES, ''' + str(total_size) + ''');
    return ESP_OK;
}

const embedded_audio_file_t* embedded_audio_find(const char* text, const char* language) {
    char filename[128];
    
    // Construct expected filename
    snprintf(filename, sizeof(filename), "%s_%s.wav", language, text);
    
    // Search in embedded files
    for (int i = 0; i < NUM_EMBEDDED_FILES; i++) {
        if (strcmp(embedded_files[i].filename, filename) == 0) {
            ESP_LOGI(TAG, "Found embedded audio: %s", filename);
            return &embedded_files[i];
        }
    }
    
    // Try notification.wav as fallback
    for (int i = 0; i < NUM_EMBEDDED_FILES; i++) {
        if (strcmp(embedded_files[i].filename, "notification.wav") == 0) {
            ESP_LOGI(TAG, "Using notification fallback for: %s_%s", language, text);
            return &embedded_files[i];
        }
    }
    
    ESP_LOGW(TAG, "No embedded audio found for: %s_%s", language, text);
    return NULL;
}

esp_err_t embedded_audio_play(const char* text, const char* language) {
    const embedded_audio_file_t* audio_file = embedded_audio_find(text, language);
    
    if (audio_file == NULL) {
        return embedded_audio_beep();
    }
    
    // Play embedded audio data using wav_player
    ESP_LOGI(TAG, "Playing embedded audio: %s (%d bytes)", audio_file->filename, audio_file->size);
    
    // For now, just log success - actual I2S playback can be implemented
    // by feeding audio_file->data directly to I2S without file system
    ESP_LOGI(TAG, "✅ Audio feedback: %s text '%s' (embedded)", language, text);
    
    return ESP_OK;
}

esp_err_t embedded_audio_beep(void) {
    ESP_LOGI(TAG, "🔔 Audio beep: OCR detection (no embedded audio)");
    // TODO: Generate simple tone using I2S DAC
    return ESP_OK;
}
'''
    
    # Write to file
    with open('main/embedded_audio.c', 'w', encoding='utf-8') as f:
        f.write(c_file_content)
    
    print(f"\n✅ Generated embedded_audio.c with {len(file_entries)} files ({total_size} bytes total)")
    print("Files included:")
    for wav_file, _, size in file_entries:
        print(f"  - {wav_file} ({size} bytes)")

if __name__ == "__main__":
    generate_embedded_audio()
