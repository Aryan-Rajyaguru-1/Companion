<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Smart Glasses OCR Project Instructions

This is an ESP-IDF project for a smart glasses clip-on module designed for visually impaired users.

## Project Context
- Target hardware: Seeed Studio XIAO ESP32S3 Sense
- Primary goal: Real-time OCR with audio feedback through A2DP Bluetooth
- Languages supported: Hindi (Devanagari), English (Latin), Gujarati
- Architecture: Dual-core ESP32S3 (Core 0: Bluetooth/comm, Core 1: Camera/ML)

## Code Style Guidelines
- Follow ESP-IDF coding conventions
- Use clear, descriptive function and variable names
- Add comprehensive error handling with ESP_ERROR_CHECK where appropriate
- Include detailed logging with appropriate log levels (ESP_LOGI, ESP_LOGW, ESP_LOGE)
- Document all public functions with proper parameter descriptions

## Key Components
1. **A2DP Audio Streaming** (`a2dp_sink.c/.h`) - Bluetooth Classic audio to glasses
2. **WAV Player** (`wav_player.c/.h`) - Playback from microSD with I2S
3. **OCR Processor** (`ocr_processor.c/.h`) - Text recognition (currently demo, needs TFLite integration)
4. **Main Application** (`main.c`) - Task management and system coordination

## Development Priorities
1. Maintain stability of A2DP audio streaming
2. Optimize memory usage (use PSRAM for large buffers)
3. Keep real-time performance (camera processing at 1-2 FPS)
4. Prepare for TensorFlow Lite Micro integration
5. Design for extensibility (navigation, object detection features)

## Memory Constraints
- ESP32S3 has 512KB SRAM + 8MB PSRAM
- Use PSRAM for: camera buffers, audio ring buffers, ML model storage
- Keep SRAM usage minimal for real-time tasks
- Models >2MB should be stored on SD card and loaded to PSRAM

## Future ML Integration Notes
- Plan for quantized int8 TensorFlow Lite models
- Target model sizes: script classifier ~50KB, CRNN models ~400KB-2MB each
- Input preprocessing: JPEG decode → crop ROI → resize → normalize
- Output post-processing: CTC decode → language model → confidence filtering

## Testing Strategy
- Use demo WAV files for audio path testing
- Implement gradual complexity in OCR (pattern matching → simple CNN → full CRNN)
- Test A2DP connectivity with various Bluetooth glasses
- Validate power consumption and thermal behavior

When suggesting code changes:
- Consider dual-core task distribution
- Ensure thread safety with appropriate FreeRTOS synchronization
- Optimize for embedded constraints (memory, processing power, battery life)
- Maintain modular design for easy feature additions
