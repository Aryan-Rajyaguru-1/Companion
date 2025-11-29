#include "wav_player.h"
#include <stdio.h>
#include <string.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/ringbuf.h>
#include <esp_log.h>
#include <esp_err.h>
#include <driver/i2s_std.h>
#include <driver/gpio.h>

static const char *TAG = "WAV_PLAYER";

#define I2S_BCK_PIN     GPIO_NUM_5
#define I2S_WS_PIN      GPIO_NUM_4
#define I2S_DATA_PIN    GPIO_NUM_6
#define I2S_SAMPLE_RATE 44100
#define I2S_SAMPLE_BITS 16
#define I2S_CHANNELS    2

#define WAV_BUFFER_SIZE 4096

// I2S channel handle
i2s_chan_handle_t tx_chan = NULL;
#define RING_BUFFER_SIZE (16 * 1024)

static RingbufHandle_t ring_buffer = NULL;
static TaskHandle_t playback_task_handle = NULL;
static bool is_playing = false;

static void playback_task(void *pvParameters) {
    size_t item_size;
    uint8_t *item;
    size_t bytes_written;
    
    while (1) {
        // Get data from ring buffer
        item = (uint8_t *)xRingbufferReceive(ring_buffer, &item_size, portMAX_DELAY);
        
        if (item != NULL) {
            // Write to I2S
            esp_err_t ret = i2s_channel_write(tx_chan, item, item_size, &bytes_written, portMAX_DELAY);
            if (ret != ESP_OK) {
                ESP_LOGE(TAG, "I2S write failed: %s", esp_err_to_name(ret));
            }
            
            // Return item to ring buffer
            vRingbufferReturnItem(ring_buffer, (void *)item);
        } else {
            // No more data, stop playing
            is_playing = false;
            vTaskSuspend(NULL);
        }
    }
}

esp_err_t wav_player_init(void) {
    ESP_LOGI(TAG, "Initializing WAV player");
    
    // Create ring buffer for audio data
    ring_buffer = xRingbufferCreate(RING_BUFFER_SIZE, RINGBUF_TYPE_BYTEBUF);
    if (ring_buffer == NULL) {
        ESP_LOGE(TAG, "Failed to create ring buffer");
        return ESP_ERR_NO_MEM;
    }
    
    // Configure I2S channel
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_AUTO, I2S_ROLE_MASTER);
    chan_cfg.dma_desc_num = 8;
    chan_cfg.dma_frame_num = 1024;
    
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, &tx_chan, NULL));
    
    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(I2S_SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = I2S_BCK_PIN,
            .ws = I2S_WS_PIN,
            .dout = I2S_DATA_PIN,
            .din = I2S_GPIO_UNUSED,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv = false,
            },
        },
    };
    
    esp_err_t ret = i2s_channel_init_std_mode(tx_chan, &std_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "I2S channel init failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    ret = i2s_channel_enable(tx_chan);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "I2S channel enable failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    // Create playback task
    xTaskCreate(
        playback_task,
        "playback_task",
        4096,
        NULL,
        5,
        &playback_task_handle
    );
    
    // Initially suspend the task
    vTaskSuspend(playback_task_handle);
    
    ESP_LOGI(TAG, "WAV player initialized successfully");
    return ESP_OK;
}

esp_err_t wav_player_play_file(const char *filename) {
    if (is_playing) {
        ESP_LOGW(TAG, "Already playing, stopping current playback");
        wav_player_stop();
    }
    
    ESP_LOGI(TAG, "Playing WAV file: %s", filename);
    
    FILE *file = fopen(filename, "rb");
    if (file == NULL) {
        ESP_LOGE(TAG, "Failed to open file: %s", filename);
        return ESP_ERR_NOT_FOUND;
    }
    
    // Read WAV header
    wav_header_t header;
    size_t read = fread(&header, sizeof(wav_header_t), 1, file);
    if (read != 1) {
        ESP_LOGE(TAG, "Failed to read WAV header");
        fclose(file);
        return ESP_ERR_INVALID_ARG;
    }
    
    // Validate WAV header
    if (strncmp(header.riff, "RIFF", 4) != 0 || 
        strncmp(header.wave, "WAVE", 4) != 0 ||
        strncmp(header.data, "data", 4) != 0) {
        ESP_LOGE(TAG, "Invalid WAV file format");
        fclose(file);
        return ESP_ERR_INVALID_ARG;
    }
    
    ESP_LOGI(TAG, "WAV info - Sample rate: %d, Channels: %d, Bits: %d, Data size: %d",
             header.sample_rate, header.num_channels, header.bits_per_sample, header.data_size);
    
    // Check if we need to resample (for now, just warn)
    if (header.sample_rate != I2S_SAMPLE_RATE) {
        ESP_LOGW(TAG, "Sample rate mismatch: file=%d, I2S=%d", header.sample_rate, I2S_SAMPLE_RATE);
    }
    
    // Read and buffer audio data
    uint8_t buffer[WAV_BUFFER_SIZE];
    size_t total_read = 0;
    
    is_playing = true;
    
    while (total_read < header.data_size) {
        size_t to_read = (header.data_size - total_read > WAV_BUFFER_SIZE) ? 
                         WAV_BUFFER_SIZE : (header.data_size - total_read);
        
        size_t bytes_read = fread(buffer, 1, to_read, file);
        if (bytes_read == 0) {
            ESP_LOGW(TAG, "Reached end of file unexpectedly");
            break;
        }
        
        // Convert mono to stereo if needed
        if (header.num_channels == 1 && I2S_CHANNELS == 2) {
            // Simple mono to stereo conversion
            for (int i = bytes_read/2 - 1; i >= 0; i--) {
                uint16_t sample = ((uint16_t*)buffer)[i];
                ((uint16_t*)buffer)[i*2] = sample;
                ((uint16_t*)buffer)[i*2+1] = sample;
            }
            bytes_read *= 2;
        }
        
        // Send data to ring buffer
        if (xRingbufferSend(ring_buffer, buffer, bytes_read, pdMS_TO_TICKS(100)) != pdTRUE) {
            ESP_LOGW(TAG, "Ring buffer full, data lost");
        }
        
        total_read += (bytes_read / (header.num_channels == 1 && I2S_CHANNELS == 2 ? 2 : 1));
    }
    
    fclose(file);
    
    // Resume playback task
    vTaskResume(playback_task_handle);
    
    ESP_LOGI(TAG, "WAV file queued for playback");
    return ESP_OK;
}

esp_err_t wav_player_stop(void) {
    if (!is_playing) {
        return ESP_OK;
    }
    
    ESP_LOGI(TAG, "Stopping WAV playback");
    
    is_playing = false;
    
    // Clear ring buffer
    uint8_t *item;
    size_t item_size;
    while ((item = (uint8_t *)xRingbufferReceive(ring_buffer, &item_size, 0)) != NULL) {
        vRingbufferReturnItem(ring_buffer, (void *)item);
    }
    
    // Suspend playback task
    vTaskSuspend(playback_task_handle);
    
    return ESP_OK;
}

bool wav_player_is_playing(void) {
    return is_playing;
}
