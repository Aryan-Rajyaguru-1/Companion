#include "a2dp_sink.h"
#include <stdio.h>
#include <string.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <esp_log.h>
#include <esp_bt.h>
#include <esp_bt_main.h>
#include <esp_bt_device.h>
#include <esp_gap_ble_api.h>
#include <nvs_flash.h>

static const char *TAG = "A2DP_SINK";

// Device name for Bluetooth discovery
#define BT_DEVICE_NAME "Smart_Glasses_OCR"

// Global state variables for A2DP connection tracking
static bool a2dp_connected = false;
static esp_a2d_connection_state_t current_connection_state = ESP_A2D_CONNECTION_STATE_DISCONNECTED;

esp_err_t a2dp_sink_init(void)
{
    ESP_LOGI(TAG, "Initializing Bluetooth for ESP32-S3 (BLE only)");
    
    esp_err_t ret;
    
    // Initialize NVS for Bluetooth
    ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    
    // Initialize Bluetooth controller for BLE only (ESP32-S3 limitation)
    esp_bt_controller_config_t bt_cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    ret = esp_bt_controller_init(&bt_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Bluetooth controller init failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    // ESP32-S3 only supports Bluetooth LE, not Classic Bluetooth A2DP
    ret = esp_bt_controller_enable(ESP_BT_MODE_BLE);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "BLE controller enable failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    ESP_LOGI(TAG, "BLE controller enabled successfully");
    
    // Initialize Bluedroid stack for BLE
    ret = esp_bluedroid_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Bluedroid init failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    ret = esp_bluedroid_enable();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Bluedroid enable failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    ESP_LOGI(TAG, "Bluedroid BLE stack initialized");
    ESP_LOGW(TAG, "A2DP Classic Bluetooth not supported on ESP32-S3");
    ESP_LOGI(TAG, "Use BLE Audio glasses or external Bluetooth transmitter");
    
    return ESP_ERR_NOT_SUPPORTED; // Indicate A2DP not available on this hardware
}

esp_err_t a2dp_sink_deinit(void)
{
    ESP_LOGI(TAG, "Deinitializing A2DP sink");
    
    esp_err_t ret = esp_bluedroid_disable();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Bluedroid disable failed: %s", esp_err_to_name(ret));
    }
    
    ret = esp_bluedroid_deinit();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Bluedroid deinit failed: %s", esp_err_to_name(ret));
    }
    
    ret = esp_bt_controller_disable();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Bluetooth controller disable failed: %s", esp_err_to_name(ret));
    }
    
    ret = esp_bt_controller_deinit();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Bluetooth controller deinit failed: %s", esp_err_to_name(ret));
    }
    
    return ESP_OK;
}

bool a2dp_sink_is_connected(void)
{
    return a2dp_connected;
}

esp_a2d_connection_state_t a2dp_sink_get_state(void)
{
    return current_connection_state;
}
