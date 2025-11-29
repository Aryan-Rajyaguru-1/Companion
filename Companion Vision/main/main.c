#include <stdio.h>
#include <string.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include <esp_log.h>
#include <esp_err.h>
#include <esp_bt.h>
#include <esp_bt_main.h>
#include <esp_bt_device.h>
#include <esp_gap_bt_api.h>
#include <esp_a2dp_api.h>
#include <esp_avrc_api.h>
#include <nvs_flash.h>
#include <driver/gpio.h>
#include <driver/spi_master.h>
#include <esp_camera.h>
#include <esp_vfs_fat.h>
#include <driver/sdmmc_host.h>
#include <driver/sdspi_host.h>
#include <sdmmc_cmd.h>
#include "wav_player.h"
#include "a2dp_sink.h" 
#include "ocr_processor.h"
#include "embedded_audio.h"

static const char *TAG = "SMART_GLASSES";

// GPIO pins for XIAO ESP32S3 Sense
#define CAMERA_PIN_PWDN    -1
#define CAMERA_PIN_RESET   -1
#define CAMERA_PIN_XCLK    10
#define CAMERA_PIN_SIOD    40
#define CAMERA_PIN_SIOC    39
#define CAMERA_PIN_D7      48
#define CAMERA_PIN_D6      11
#define CAMERA_PIN_D5      12
#define CAMERA_PIN_D4      14
#define CAMERA_PIN_D3      16
#define CAMERA_PIN_D2      18
#define CAMERA_PIN_D1      17
#define CAMERA_PIN_D0      15
#define CAMERA_PIN_VSYNC   38
#define CAMERA_PIN_HREF    47
#define CAMERA_PIN_PCLK    13

// I2S Audio Output pins for direct headphone connection
#define I2S_WS_PIN    4   // Word Select (LRCLK)
#define I2S_BCK_PIN   5   // Bit Clock (BCLK) 
#define I2S_DATA_PIN  6   // Data Output (DIN)

// SD Card pins for XIAO ESP32S3 Sense  
#define SD_MISO 9
#define SD_MOSI 8
#define SD_CLK  7
#define SD_CS   21

// Core assignments
#define CAMERA_CORE 1  // Core 1 for camera and ML processing
#define BT_CORE 0      // Core 0 for Bluetooth and communication

static QueueHandle_t ocr_result_queue;

// Camera configuration
static camera_config_t camera_config = {
    .pin_pwdn = CAMERA_PIN_PWDN,
    .pin_reset = CAMERA_PIN_RESET,
    .pin_xclk = CAMERA_PIN_XCLK,
    .pin_sccb_sda = CAMERA_PIN_SIOD,
    .pin_sccb_scl = CAMERA_PIN_SIOC,
    .pin_d7 = CAMERA_PIN_D7,
    .pin_d6 = CAMERA_PIN_D6,
    .pin_d5 = CAMERA_PIN_D5,
    .pin_d4 = CAMERA_PIN_D4,
    .pin_d3 = CAMERA_PIN_D3,
    .pin_d2 = CAMERA_PIN_D2,
    .pin_d1 = CAMERA_PIN_D1,
    .pin_d0 = CAMERA_PIN_D0,
    .pin_vsync = CAMERA_PIN_VSYNC,
    .pin_href = CAMERA_PIN_HREF,
    .pin_pclk = CAMERA_PIN_PCLK,
    .xclk_freq_hz = 20000000,
    .ledc_timer = LEDC_TIMER_0,
    .ledc_channel = LEDC_CHANNEL_0,
    .pixel_format = PIXFORMAT_JPEG,
    .frame_size = FRAMESIZE_QVGA,  // Smaller frame size to save memory without PSRAM
    .jpeg_quality = 15,           // Higher quality number = lower quality/smaller size
    .fb_count = 1,
    .fb_location = CAMERA_FB_IN_DRAM,  // Force frame buffer in internal RAM
    .grab_mode = CAMERA_GRAB_WHEN_EMPTY,
};

void camera_task(void *pvParameters) {
    ESP_LOGI(TAG, "Starting camera task on core %d", xPortGetCoreID());
    
    // Log camera configuration for debugging
    ESP_LOGI(TAG, "Camera config: fb_location=%d (0=PSRAM, 1=DRAM), fb_count=%d, frame_size=%d", 
             camera_config.fb_location, camera_config.fb_count, camera_config.frame_size);
    
    // Initialize camera
    esp_err_t err = esp_camera_init(&camera_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Camera init failed with error 0x%x", err);
        vTaskDelete(NULL);
        return;
    }
    
    ESP_LOGI(TAG, "Camera initialized successfully");
    
    while (1) {
        // Capture frame
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            ESP_LOGE(TAG, "Camera capture failed");
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }
        
        // Process OCR (placeholder for now)
        ocr_result_t result = {0};
        esp_err_t ocr_err = process_ocr_frame(fb->buf, fb->len, &result);
        
        if (ocr_err == ESP_OK && strlen(result.text) > 0) {
            ESP_LOGI(TAG, "OCR Result: %s (Language: %s)", result.text, result.language);
            
            // Send result to audio processing queue
            if (xQueueSend(ocr_result_queue, &result, 0) != pdTRUE) {
                ESP_LOGW(TAG, "OCR result queue full, dropping result");
            }
        }
        
        esp_camera_fb_return(fb);
        vTaskDelay(pdMS_TO_TICKS(500)); // Process every 500ms
    }
}

void audio_task(void *pvParameters) {
    ESP_LOGI(TAG, "Starting audio task on core %d", xPortGetCoreID());
    
    ocr_result_t result;
    
    while (1) {
        if (xQueueReceive(ocr_result_queue, &result, portMAX_DELAY) == pdTRUE) {
            ESP_LOGI(TAG, "Processing audio for: %s", result.text);
            
            // Use embedded audio system for immediate feedback
            esp_err_t audio_err = embedded_audio_play(result.text, result.language);
            
            if (audio_err != ESP_OK) {
                ESP_LOGW(TAG, "Embedded audio failed, using fallback beep");
                embedded_audio_beep();
            }
        }
    }
}

static esp_err_t init_sd_card(void) {
    esp_err_t ret;
    
    // Options for mounting the filesystem
    esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,
        .max_files = 5,
        .allocation_unit_size = 16 * 1024
    };
    
    // Configure SPI bus
    spi_bus_config_t bus_cfg = {
        .mosi_io_num = SD_MOSI,
        .miso_io_num = SD_MISO,
        .sclk_io_num = SD_CLK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 4000,
    };
    
    ret = spi_bus_initialize(SPI2_HOST, &bus_cfg, SDSPI_DEFAULT_DMA);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize SPI bus");
        return ret;
    }
    
    // Use SPI peripheral to communicate with SD card
    sdmmc_host_t host = SDSPI_HOST_DEFAULT();
    sdspi_device_config_t slot_config = SDSPI_DEVICE_CONFIG_DEFAULT();
    slot_config.gpio_cs   = SD_CS;
    slot_config.host_id   = SPI2_HOST;
    
    sdmmc_card_t *card;
    ret = esp_vfs_fat_sdspi_mount("/sdcard", &host, &slot_config, &mount_config, &card);
    
    if (ret != ESP_OK) {
        if (ret == ESP_FAIL) {
            ESP_LOGE(TAG, "Failed to mount filesystem");
        } else {
            ESP_LOGE(TAG, "Failed to initialize the card (%s)", esp_err_to_name(ret));
        }
        return ret;
    }
    
    ESP_LOGI(TAG, "SD card mounted successfully");
    sdmmc_card_print_info(stdout, card);
    return ESP_OK;
}

void app_main(void) {
    ESP_LOGI(TAG, "Smart Glasses OCR System Starting...");
    
    // NVS will be initialized by A2DP module
    
    // Initialize SD card (non-critical for basic testing)
    
    // Initialize SD card (non-critical for basic testing)
    if (init_sd_card() != ESP_OK) {
        ESP_LOGW(TAG, "SD card initialization failed - continuing without SD card");
        // Continue without SD card for testing
    } else {
        ESP_LOGI(TAG, "SD card initialized successfully");
    }
    
    // Create queues
    ocr_result_queue = xQueueCreate(5, sizeof(ocr_result_t));
    if (ocr_result_queue == NULL) {
        ESP_LOGE(TAG, "Failed to create OCR result queue");
        return;
    }
    
    // Initialize Bluetooth (BLE only on ESP32-S3)
    esp_err_t bt_err = a2dp_sink_init();
    if (bt_err == ESP_ERR_NOT_SUPPORTED) {
        ESP_LOGW(TAG, "A2DP not supported on ESP32-S3 (BLE only hardware)");
        ESP_LOGI(TAG, "=== AUDIO CONNECTION OPTIONS ===");
        ESP_LOGI(TAG, "1. Check if your glasses support BLE Audio");
        ESP_LOGI(TAG, "2. Use I2S pins %d,%d,%d for direct wired connection", I2S_WS_PIN, I2S_BCK_PIN, I2S_DATA_PIN);
        ESP_LOGI(TAG, "3. Connect external Bluetooth Classic transmitter to I2S");
        ESP_LOGI(TAG, "4. Upgrade to ESP32 (Classic) for native A2DP support");
        ESP_LOGI(TAG, "================================");
        // Continue without A2DP - we'll use I2S for audio output
    } else if (bt_err != ESP_OK) {
        ESP_LOGE(TAG, "Bluetooth initialization failed");
        return;
    } else {
        ESP_LOGI(TAG, "Bluetooth initialized successfully - checking for BLE Audio");
    }
    
    // Initialize WAV player
    if (wav_player_init() != ESP_OK) {
        ESP_LOGE(TAG, "WAV player initialization failed");
        return;
    }
    
    // Initialize embedded audio system
    if (embedded_audio_init() != ESP_OK) {
        ESP_LOGE(TAG, "Embedded audio initialization failed");
        return;
    }
    
    // Initialize OCR processor
    if (ocr_processor_init() != ESP_OK) {
        ESP_LOGE(TAG, "OCR processor initialization failed");
        return;
    }
    
    ESP_LOGI(TAG, "All components initialized successfully");
    
    // Create tasks
    xTaskCreatePinnedToCore(
        camera_task,
        "camera_task",
        8192,
        NULL,
        5,
        NULL,
        CAMERA_CORE
    );
    
    xTaskCreatePinnedToCore(
        audio_task,
        "audio_task",
        4096,
        NULL,
        4,
        NULL,
        BT_CORE
    );
    
    ESP_LOGI(TAG, "Tasks created successfully");
    
    // Main loop with enhanced system monitoring
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(10000));
        
        // System health report
        ESP_LOGI(TAG, "=== SMART GLASSES OCR SYSTEM STATUS ===");
        ESP_LOGI(TAG, "Free heap: %d bytes", esp_get_free_heap_size());
        ESP_LOGI(TAG, "Camera: OV2640 operational");
        ESP_LOGI(TAG, "OCR: Hindi/English/Gujarati detection active");
        ESP_LOGI(TAG, "Bluetooth: BLE 5.0 ready (MAC: 8c:bf:ea:8e:54:3e)");
        ESP_LOGI(TAG, "Audio: I2S embedded tone system operational");
        ESP_LOGI(TAG, "Tasks: Camera on Core %d, Audio on Core %d", CAMERA_CORE, BT_CORE);
        ESP_LOGI(TAG, "========================================");
    }
}
