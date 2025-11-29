#!/usr/bin/env python3
"""
Simple Bluetooth LE scanner to check if smart glasses support BLE Audio
"""

import asyncio
from bleak import BleakScanner

async def scan_for_glasses():
    print("Scanning for Bluetooth LE devices (including smart glasses)...")
    print("Looking for devices that might support BLE Audio...")
    
    devices = await BleakScanner.discover(timeout=10.0)
    
    audio_keywords = ['glass', 'audio', 'headphone', 'speaker', 'sound', 'rhythm', 'conekt']
    
    print(f"\nFound {len(devices)} BLE devices:")
    print("-" * 50)
    
    for device in devices:
        name = device.name or "Unknown"
        address = device.address
        rssi = device.rssi
        
        is_audio_device = any(keyword.lower() in name.lower() for keyword in audio_keywords)
        
        if is_audio_device:
            print(f"🎧 AUDIO DEVICE: {name}")
        else:
            print(f"📱 {name}")
            
        print(f"   Address: {address}")
        print(f"   RSSI: {rssi} dBm")
        print()

if __name__ == "__main__":
    try:
        asyncio.run(scan_for_glasses())
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure bluetooth is enabled and you have permissions")
