#ifndef WAV_PLAYER_H
#define WAV_PLAYER_H

#include <esp_err.h>
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief WAV file header structure
 */
typedef struct {
    char riff[4];           // "RIFF"
    uint32_t file_size;     // File size - 8
    char wave[4];           // "WAVE"
    char fmt[4];            // "fmt "
    uint32_t fmt_size;      // Format chunk size
    uint16_t audio_format;  // Audio format (1 = PCM)
    uint16_t num_channels;  // Number of channels
    uint32_t sample_rate;   // Sample rate
    uint32_t byte_rate;     // Byte rate
    uint16_t block_align;   // Block align
    uint16_t bits_per_sample; // Bits per sample
    char data[4];           // "data"
    uint32_t data_size;     // Data size
} __attribute__((packed)) wav_header_t;

/**
 * @brief Initialize WAV player
 * @return ESP_OK on success
 */
esp_err_t wav_player_init(void);

/**
 * @brief Play WAV file from SD card
 * @param filename Path to WAV file (e.g., "/sdcard/test.wav")
 * @return ESP_OK on success
 */
esp_err_t wav_player_play_file(const char *filename);

/**
 * @brief Stop current playback
 * @return ESP_OK on success
 */
esp_err_t wav_player_stop(void);

/**
 * @brief Check if player is currently playing
 * @return true if playing, false otherwise
 */
bool wav_player_is_playing(void);

#ifdef __cplusplus
}
#endif

#endif // WAV_PLAYER_H
