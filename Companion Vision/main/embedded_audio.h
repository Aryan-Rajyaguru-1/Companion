#ifndef EMBEDDED_AUDIO_H
#define EMBEDDED_AUDIO_H

#include <stdint.h>
#include <esp_err.h>

// Audio file structure
typedef struct {
    const char* filename;
    const uint8_t* data;
    size_t size;
} embedded_audio_file_t;

// Function declarations
esp_err_t embedded_audio_init(void);
esp_err_t embedded_audio_play(const char* text, const char* language);
const embedded_audio_file_t* embedded_audio_find(const char* text, const char* language);

// Generate simple beep tone if no audio file found
esp_err_t embedded_audio_beep(void);

// Generate specific tone (frequency in Hz, duration in ms)
esp_err_t embedded_audio_generate_tone(int frequency, int duration_ms);

#endif // EMBEDDED_AUDIO_H
