# Smart Glasses OCR System

An ESP-IDF based smart glasses clip-on module for visually impaired users, featuring real-time OCR with audio feedback through A2DP Bluetooth streaming.

## Features

- **Real-time OCR**: Process camera frames for text recognition (Hindi, English, Gujarati)
- **A2DP Audio Streaming**: Stream audio directly to Bluetooth glasses
- **Dual-core Processing**: Core 0 for Bluetooth/communication, Core 1 for camera/ML
- **WAV Playback**: Pre-recorded multilingual audio prompts from microSD
- **Modular Design**: Extensible architecture for additional features

## Hardware Requirements

- Seeed Studio XIAO ESP32S3 Sense
- MicroSD card (32GB recommended)
- Bluetooth A2DP compatible glasses/headphones
- Optional: MPU6050 IMU for future navigation features

## Pin Configuration (XIAO ESP32S3 Sense)

### Camera (OV2640)
- XCLK: GPIO 10
- SIOD: GPIO 40 (SDA)
- SIOC: GPIO 39 (SCL)
- Data pins: GPIO 15,17,18,16,14,12,11,48
- VSYNC: GPIO 38
- HREF: GPIO 47
- PCLK: GPIO 13

### SD Card (SPI)
- MISO: GPIO 9
- MOSI: GPIO 8
- CLK: GPIO 7
- CS: GPIO 21

### I2S Audio (for internal processing)
- BCK: GPIO 1
- WS: GPIO 2
- DATA: GPIO 3

## Software Architecture

### Core 0 Tasks
- Bluetooth A2DP stack management
- Audio processing and streaming
- SD card file operations
- System monitoring

### Core 1 Tasks
- Camera frame capture
- OCR processing (TensorFlow Lite Micro)
- Image preprocessing
- ML inference

## Getting Started

### 1. Environment Setup

```bash
# Install ESP-IDF (v5.0 or later)
mkdir -p ~/esp
cd ~/esp
git clone --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh esp32s3

# Set up environment
. ./export.sh
```

### 2. Build and Flash

```bash
# Clone and build
cd /path/to/smart-glasses-ocr
idf.py set-target esp32s3
idf.py build

# Flash to device
idf.py -p /dev/ttyUSB0 flash monitor
```

### 3. Prepare SD Card

```bash
# Generate sample WAV files
python generate_sample_wavs.py

# Copy to SD card (format as FAT32)
cp sample_wavs/*.wav /media/sdcard/
```

### 4. Pair Bluetooth Glasses

1. Power on your A2DP Bluetooth glasses
2. Put them in pairing mode
3. Power on the XIAO ESP32S3 device
4. Device will appear as "Smart_Glasses_OCR"
5. Complete pairing (PIN: 1234 if required)

## Configuration

### OCR Settings
```c
// In ocr_processor.c, adjust ROI for your use case
ocr_set_roi(100, 100, 440, 280);  // x, y, width, height
```

### Audio Settings
```c
// In wav_player.c, adjust sample rate if needed
#define I2S_SAMPLE_RATE 44100  // Match your WAV files
```

### Bluetooth Settings
```c
// In a2dp_sink.c, change device name
#define BT_DEVICE_NAME "Smart_Glasses_OCR"
```

## File Structure

```
├── main/
│   ├── main.c              # Main application and task management
│   ├── wav_player.c/.h     # WAV file playback from SD card
│   ├── a2dp_sink.c/.h      # A2DP Bluetooth audio streaming
│   ├── ocr_processor.c/.h  # OCR processing (demo implementation)
│   └── CMakeLists.txt      # Component build configuration
├── sample_wavs/            # Sample audio files
├── generate_sample_wavs.py # Audio file generator script
├── CMakeLists.txt          # Project build configuration
├── sdkconfig.defaults      # ESP-IDF configuration
└── README.md               # This file
```

## Current Implementation Status

### ✅ Completed
- ESP-IDF project structure
- A2DP Bluetooth audio streaming
- WAV file playback from microSD
- Basic camera integration
- Dual-core task management
- Demo OCR processing

### 🚧 In Development
- TensorFlow Lite Micro integration
- Real CRNN models for Hindi/English/Gujarati
- Image preprocessing pipeline
- Text-to-audio mapping improvements

### 📋 Planned Features
- Step counting and navigation
- GPS/NavIC integration
- Object detection
- Traffic signal recognition
- Bus route identification
- Currency detection

## Development Notes

### Memory Usage
- Use PSRAM for large buffers (camera frames, audio buffers)
- Store models on SD card if >2MB, load to PSRAM for inference
- Keep working memory usage under 256KB in SRAM

### Performance Targets
- Camera frame processing: 1-2 FPS
- OCR inference: 200-400ms per frame
- Audio latency: <500ms from detection to playback
- Power consumption: <200mA average

### Real OCR Implementation
The current OCR processor is a demo. For production:
1. Train CRNN models for each script (Devanagari, Latin, Gujarati)
2. Implement script classifier
3. Add TensorFlow Lite Micro integration
4. Create preprocessing pipeline (JPEG decode, crop, resize, normalize)
5. Add post-processing (beam search, dictionary lookup)

## Troubleshooting

### Build Issues
```bash
# Clean and rebuild
idf.py clean
idf.py build

# Check target is set correctly
idf.py set-target esp32s3
```

### Bluetooth Connection Issues
- Ensure glasses support A2DP sink profile
- Check device is discoverable
- Try removing previous pairings
- Verify PIN code (default: 1234)

### SD Card Issues
- Format as FAT32
- Check wiring connections
- Verify 3.3V power supply
- Test with smaller capacity card

### Audio Issues
- Check WAV file format (44.1kHz, 16-bit PCM)
- Verify A2DP connection status
- Test with simple notification sounds first
- Check I2S pin configuration

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Update documentation
5. Submit pull request

## License

This project is open source. Please check individual component licenses for details.

## Support

For hardware support: [Seeed Studio XIAO ESP32S3 Documentation](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/)

For ESP-IDF support: [ESP-IDF Programming Guide](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/)
