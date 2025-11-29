#include "a2dp_sink.h"
#include <stdio.h>
#include <string.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <esp_log.h>
#include <esp_bt.h>
#include <esp_bt_main.h>
#include <esp_bt_device.h>
#include <esp_gap_bt_api.h>
#include <esp_a2dp_api.h>
#include <esp_avrc_api.h>
#include <nvs_flash.h>

static const char *TAG = "A2DP_SINK";

// Device name for Bluetooth discovery
#define BT_DEVICE_NAME "Smart_Glasses_OCR"

static esp_a2d_connection_state_t s_a2dp_state = ESP_A2D_CONNECTION_STATE_DISCONNECTED;
static bool s_a2dp_connected = false;

// A2DP callback function
static void a2dp_callback(esp_a2d_cb_event_t event, esp_a2d_cb_param_t *param) {
    esp_a2d_cb_param_t *a2dp = NULL;
    
    switch (event) {
        case ESP_A2D_CONNECTION_STATE_EVT: {
            a2dp = (esp_a2d_cb_param_t *)(param);
            uint8_t *bda = a2dp->conn_stat.remote_bda;
            ESP_LOGI(TAG, "A2DP connection state: %s, [%02x:%02x:%02x:%02x:%02x:%02x]",
                     (a2dp->conn_stat.state == ESP_A2D_CONNECTION_STATE_CONNECTED) ? "Connected" : "Disconnected",
                     bda[0], bda[1], bda[2], bda[3], bda[4], bda[5]);
            
            s_a2dp_state = a2dp->conn_stat.state;
            s_a2dp_connected = (s_a2dp_state == ESP_A2D_CONNECTION_STATE_CONNECTED);
            
            if (s_a2dp_connected) {
                ESP_LOGI(TAG, "A2DP Connected to Bluetooth glasses");
            } else {
                ESP_LOGI(TAG, "A2DP Disconnected from Bluetooth glasses");
            }
            break;
        }
        case ESP_A2D_AUDIO_STATE_EVT: {
            a2dp = (esp_a2d_cb_param_t *)(param);
            ESP_LOGI(TAG, "Audio state: %s",
                     (a2dp->audio_stat.state == ESP_A2D_AUDIO_STATE_STARTED) ? "Started" : "Stopped");
            break;
        }
        case ESP_A2D_AUDIO_CFG_EVT: {
            a2dp = (esp_a2d_cb_param_t *)(param);
            ESP_LOGI(TAG, "Audio codec config");
            
            if (a2dp->audio_cfg.mcc.type == ESP_A2D_MCT_SBC) {
                ESP_LOGI(TAG, "SBC codec configured - using default 44.1kHz sample rate");
                // For smart glasses, standard Bluetooth audio rate
            }
            break;
        }
        default:
            ESP_LOGD(TAG, "Unhandled A2DP event: %d", event);
            break;
    }
}

// GAP callback function
static void gap_callback(esp_bt_gap_cb_event_t event, esp_bt_gap_cb_param_t *param) {
    switch (event) {
        case ESP_BT_GAP_AUTH_CMPL_EVT: {
            if (param->auth_cmpl.stat == ESP_BT_STATUS_SUCCESS) {
                ESP_LOGI(TAG, "Authentication success: %s", param->auth_cmpl.device_name);
                ESP_LOG_BUFFER_HEX(TAG, param->auth_cmpl.bda, ESP_BD_ADDR_LEN);
            } else {
                ESP_LOGE(TAG, "Authentication failed, status:%d", param->auth_cmpl.stat);
            }
            break;
        }
        case ESP_BT_GAP_PIN_REQ_EVT: {
            ESP_LOGI(TAG, "PIN request");
            if (param->pin_req.min_16_digit) {
                ESP_LOGI(TAG, "Input pin code: 0000 0000 0000 0000");
                esp_bt_pin_code_t pin_code = {0};
                esp_bt_gap_pin_reply(param->pin_req.bda, true, 16, pin_code);
            } else {
                ESP_LOGI(TAG, "Input pin code: 1234");
                esp_bt_pin_code_t pin_code;
                pin_code[0] = '1';
                pin_code[1] = '2';
                pin_code[2] = '3';
                pin_code[3] = '4';
                esp_bt_gap_pin_reply(param->pin_req.bda, true, 4, pin_code);
            }
            break;
        }
        case ESP_BT_GAP_MODE_CHG_EVT:
            ESP_LOGI(TAG, "Bluetooth mode changed to: %d", param->mode_chg.mode);
            break;
        default:
            ESP_LOGD(TAG, "Unhandled GAP event: %d", event);
            break;
    }
}

esp_err_t a2dp_sink_init(void) {
    ESP_LOGI(TAG, "Initializing A2DP sink for Bluetooth glasses");
    
    esp_err_t ret;
    
    // Initialize NVS for BT
    ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    
    // Initialize Bluetooth controller
    esp_bt_controller_config_t bt_cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    ret = esp_bt_controller_init(&bt_cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Bluetooth controller init failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    ret = esp_bt_controller_enable(ESP_BT_MODE_CLASSIC_BT);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Bluetooth controller enable failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    // Initialize Bluedroid stack
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
    
    // Register A2DP callback
    ret = esp_a2d_register_callback(a2dp_callback);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "A2DP callback registration failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    // Initialize A2DP source
    ret = esp_a2d_source_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "A2DP source init failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    // Set device name
    ret = esp_bt_gap_set_device_name(BT_DEVICE_NAME);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Set device name failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    // Register GAP callback
    ret = esp_bt_gap_register_callback(gap_callback);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "GAP callback registration failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    // Set discoverable and connectable mode
    ret = esp_bt_gap_set_scan_mode(ESP_BT_CONNECTABLE, ESP_BT_GENERAL_DISCOVERABLE);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Set scan mode failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    ESP_LOGI(TAG, "A2DP sink initialization completed");
    ESP_LOGI(TAG, "Device '%s' is discoverable and ready for pairing", BT_DEVICE_NAME);
    
    return ESP_OK;
}

esp_err_t a2dp_sink_deinit(void) {
    ESP_LOGI(TAG, "Deinitializing A2DP sink");
    
    esp_err_t ret = esp_a2d_source_deinit();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "A2DP source deinit failed: %s", esp_err_to_name(ret));
    }
    
    ret = esp_bluedroid_disable();
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

esp_err_t a2dp_sink_disconnect_all(void) {
    ESP_LOGI(TAG, "Disconnecting all A2DP connections");
    
    // Reset state
    s_a2dp_state = ESP_A2D_CONNECTION_STATE_DISCONNECTED;
    s_a2dp_connected = false;
    
    return ESP_OK;
}

bool a2dp_sink_is_connected(void) {
    return s_a2dp_connected;
}

esp_a2d_connection_state_t a2dp_sink_get_state(void) {
    return s_a2dp_state;
}
