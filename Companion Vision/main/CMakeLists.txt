idf_component_register(SRCS "main.c" "wav_player.c" "a2dp_sink.c" "ocr_processor.c" "embedded_audio.c"
                    INCLUDE_DIRS "."
                    REQUIRES driver fatfs bt esp_adc nvs_flash esp_driver_i2s esp_driver_sdmmc)
