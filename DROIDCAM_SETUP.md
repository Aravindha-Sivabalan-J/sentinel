# DroidCam Setup Instructions

## The "Error Creating Image Encoder" Problem

This error means your phone CANNOT encode video at the current settings. Follow these steps:

### Step 1: Fix DroidCam App Settings

1. **Open DroidCam app on your phone**
2. **Tap the 3 dots (menu) → Settings**
3. **Change these settings:**
   - Video Resolution: **352x288** (lowest option)
   - Video Quality: **Low** or **Medium**
   - FPS: **15** or **Auto**
   - Turn OFF "Use H.264" if present
   - Turn OFF "Hardware Encoder" if present

### Step 2: Restart Everything

1. **Force close DroidCam app** (don't just minimize)
2. **Reopen DroidCam**
3. **Verify the WiFi IP shown** (should be 192.168.1.25)
4. **Restart your Django server**

### Step 3: Test Connection

Run this command:
```bash
curl http://192.168.1.25:4747/ | grep -i droidcam
```

If you see "DroidCam" in the output, it's working.

### Step 4: If Still Not Working

1. **Restart your phone**
2. **Check camera permissions** for DroidCam
3. **Try switching camera** (front/back) in DroidCam settings
4. **Disable battery optimization** for DroidCam app
5. **Check if another app is using the camera**

### Common Issues

- **"DroidCam busy"**: Another client is connected. Click "Take Over" in browser or use /override endpoint
- **Connection timeout**: Phone and computer not on same WiFi
- **Wrong IP**: Check the IP shown in DroidCam app matches your code
