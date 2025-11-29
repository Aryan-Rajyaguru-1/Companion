#ifndef OCR_PROCESSOR_H
#define OCR_PROCESSOR_H

#include <esp_err.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define OCR_MAX_TEXT_LENGTH 256
#define OCR_MAX_LANGUAGE_LENGTH 16

/**
 * @brief OCR result structure
 */
typedef struct {
    char text[OCR_MAX_TEXT_LENGTH];         // Recognized text
    char language[OCR_MAX_LANGUAGE_LENGTH]; // Detected language (hindi, english, gujarati)
    float confidence;                        // Confidence score (0.0 - 1.0)
    uint32_t processing_time_ms;            // Processing time in milliseconds
} ocr_result_t;

/**
 * @brief Initialize OCR processor
 * @return ESP_OK on success
 */
esp_err_t ocr_processor_init(void);

/**
 * @brief Process OCR on camera frame
 * @param frame_buffer JPEG frame buffer
 * @param frame_size Size of frame buffer
 * @param result Pointer to store OCR result
 * @return ESP_OK on success
 */
esp_err_t process_ocr_frame(uint8_t *frame_buffer, size_t frame_size, ocr_result_t *result);

/**
 * @brief Deinitialize OCR processor
 * @return ESP_OK on success
 */
esp_err_t ocr_processor_deinit(void);

/**
 * @brief Set OCR region of interest (ROI)
 * @param x X coordinate of ROI
 * @param y Y coordinate of ROI
 * @param width Width of ROI
 * @param height Height of ROI
 * @return ESP_OK on success
 */
esp_err_t ocr_set_roi(int x, int y, int width, int height);

#ifdef __cplusplus
}
#endif

#endif // OCR_PROCESSOR_H
