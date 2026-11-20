"""
NitroTracker / DS Sampler Converter utility.
Converts audio files to 16kHz, Mono, 16-bit WAV for Nintendo DS homebrew compatibility.
"""
import os
import soundfile as sf
import scipy.signal
import numpy as np

def convert_to_nitro(root_folder):
    """
    Recursively convert all .wav files in root_folder to:
    - Sample Rate: 16000 Hz
    - Channels: 1 (Mono)
    - Bit Depth: 16-bit PCM
    """
    TARGET_SR = 16000
    
    print(f"[FiggyGen] NitroTracker Conversion started for: {root_folder}")
    print(f"[FiggyGen] Target: {TARGET_SR}Hz | Mono | 16-bit PCM")

    count = 0
    errors = 0

    for subdir, dirs, files in os.walk(root_folder):
        for file in files:
            if file.lower().endswith(".wav"):
                file_path = os.path.join(subdir, file)
                
                try:
                    # Read audio
                    data, samplerate = sf.read(file_path)
                    
                    # 1. Convert to Mono
                    # data shape is (frames, channels) if multichannel
                    if len(data.shape) > 1 and data.shape[1] > 1:
                        # Average channels to get mono
                        data = np.mean(data, axis=1)
                    
                    # 2. Resample if necessary
                    if samplerate != TARGET_SR:
                        # Calculate number of samples in new rate
                        # new_len = int(len(data) * TARGET_SR / samplerate)
                        # data = scipy.signal.resample(data, new_len)
                        
                        # Preferred method: resample_poly (up/down integer ratio, or float approx)
                        # But for arbitrary float ratio, 'resample' (FFT) is easier if we don't care about memory on huge files.
                        # For short samples, fft resample is fine.
                        # Let's use simple calculation.
                        number_of_samples = round(len(data) * float(TARGET_SR) / samplerate)
                        data = scipy.signal.resample(data, number_of_samples)
                        
                    # 3. Export as 16-bit PCM
                    # soundfile handles clipping/dither automatically-ish if we just pass float?
                    # It's safer to clip manually to avoid wrap-around or weirdness if signal > 1.0
                    if data.max() > 1.0 or data.min() < -1.0:
                        data = np.clip(data, -1.0, 1.0)
                        
                    sf.write(file_path, data, TARGET_SR, subtype='PCM_16')
                    print(f"  [OK] {file}")
                    count += 1
                    
                except Exception as e:
                    print(f"  [ERR] Could not convert {file}: {e}")
                    errors += 1

    print(f"\n[FiggyGen] Conversion complete.")
    print(f"  Processed: {count}")
    print(f"  Errors:    {errors}")

