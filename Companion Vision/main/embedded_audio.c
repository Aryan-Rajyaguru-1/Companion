/*
 * Simple Embedded Audio System for Smart Glasses OCR
 * Provides audio feedback without requiring SD card or external storage
 */

#include "embedded_audio.h"
#include "wav_player.h"
#include <string.h>
#include <esp_log.h>
#include <driver/i2s_std.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <math.h>

static const char *TAG = "EMBEDDED_AUDIO";

// External I2S channel handle from wav_player
extern i2s_chan_handle_t tx_chan;

esp_err_t embedded_audio_init(void) {
    ESP_LOGI(TAG, "Embedded audio system initialized (tone generation mode)");
    return ESP_OK;
}

// Generate a simple tone pattern for different languages/words
esp_err_t embedded_audio_play(const char* text, const char* language) {
    ESP_LOGI(TAG, "🔊 Playing audio feedback for: %s text '%s'", language, text);
    
    // Create different tone patterns based on language
    int frequency = 800;  // Base frequency
    int pattern_length = 2; // Number of beeps
    
    if (strcmp(language, "hindi") == 0) {
        frequency = 600;  // Lower tone for Hindi
        pattern_length = 3;
    } else if (strcmp(language, "gujarati") == 0) {
        frequency = 1000; // Higher tone for Gujarati  
        pattern_length = 2;
    } else {
        frequency = 800;  // Medium tone for English
        pattern_length = 1;
    }
    
    // Generate tone pattern
    for (int i = 0; i < pattern_length; i++) {
        embedded_audio_generate_tone(frequency + (i * 100), 200); // 200ms beep
        if (i < pattern_length - 1) {
            vTaskDelay(pdMS_TO_TICKS(100)); // 100ms pause between beeps
        }
    }
    
    return ESP_OK;
}

esp_err_t embedded_audio_beep(void) {
    ESP_LOGI(TAG, "🔔 Generic audio beep");
    return embedded_audio_generate_tone(800, 300);
}

esp_err_t embedded_audio_generate_tone(int frequency, int duration_ms) {
    if (tx_chan == NULL) {
        ESP_LOGW(TAG, "I2S not initialized, cannot generate tone");
        return ESP_ERR_INVALID_STATE;
    }
    
    const int sample_rate = 44100;
    const int samples = (sample_rate * duration_ms) / 1000;
    
    // Generate sine wave samples
    int16_t *audio_buffer = malloc(samples * 2 * sizeof(int16_t)); // Stereo
    if (audio_buffer == NULL) {
        ESP_LOGE(TAG, "Failed to allocate audio buffer");
        return ESP_ERR_NO_MEM;
    }
    
    for (int i = 0; i < samples; i++) {
        float t = (float)i / sample_rate;
        int16_t sample = (int16_t)(sin(2.0 * M_PI * frequency * t) * 16000); // Amplitude 16000
        
        // Apply envelope to avoid clicks (fade in/out)
        if (i < samples / 10) {
            sample = sample * i / (samples / 10);
        } else if (i > samples - samples / 10) {
            sample = sample * (samples - i) / (samples / 10);
        }
        
        audio_buffer[i * 2] = sample;     // Left channel
        audio_buffer[i * 2 + 1] = sample; // Right channel
    }
    
    // Send to I2S
    size_t bytes_written;
    esp_err_t ret = i2s_channel_write(tx_chan, audio_buffer, 
                                      samples * 2 * sizeof(int16_t), 
                                      &bytes_written, portMAX_DELAY);
    
    free(audio_buffer);
    
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "I2S write failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    ESP_LOGI(TAG, "Generated %dHz tone for %dms (%d bytes written)", 
             frequency, duration_ms, bytes_written);
    
    return ESP_OK;
}

const embedded_audio_file_t* embedded_audio_find(const char* text, const char* language) {
    // For tone generation mode, we don't use file lookup
    return NULL;
}
