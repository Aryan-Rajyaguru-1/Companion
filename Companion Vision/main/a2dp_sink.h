#ifndef A2DP_SINK_H
#define A2DP_SINK_H

#include <esp_err.h>
#include <esp_a2dp_api.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Initialize A2DP sink for streaming audio to Bluetooth glasses
 * @return ESP_OK on success
 */
esp_err_t a2dp_sink_init(void);

/**
 * @brief Deinitialize A2DP sink
 * @return ESP_OK on success
 */
esp_err_t a2dp_sink_deinit(void);

/**
 * @brief Check if A2DP is connected
 * @return true if connected, false otherwise
 */
bool a2dp_sink_is_connected(void);

/**
 * @brief Get the current A2DP connection state
 * @return esp_a2d_connection_state_t
 */
esp_a2d_connection_state_t a2dp_sink_get_state(void);

#ifdef __cplusplus
}
#endif

#endif // A2DP_SINK_H
