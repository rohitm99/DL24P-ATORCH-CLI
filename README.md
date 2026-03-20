Python controller for ATORCH DL24P electronic load with **READ and WRITE** capabilities. This is for the V1.1.0 DL24P ATORCH load tester available on Amazon. This is a WIP with MOSTLY complete functionality for the DL24P device. Certain commands and registers have not yet been completed, but only due to lack of time. Feel free to use this code as a starting point for exploration, and potentially contributing to the full control of this device with findings updated here!

Reverse engineered the **write command protocol** using Wireshark USB captures through Windows software provided by ATORCH vendor.

### Write Command Format
```
55 05 01 [REGISTER] [VALUE_4_BYTES_BIG_ENDIAN] 00 00 00 ee ff [pad to 91 bytes]
```

**Example - Setting voltage cutoff to 5.0V:**
```
55 05 01 29 40 a0 00 00 ee ff 00 00 00 ... [zeros to 91 bytes]
```
Where:
- `55 05` = Header/sync bytes
- `01` = Write command
- `29` = Register address (voltage cutoff)
- `40 a0 00 00` = 5.0 as big-endian float
- `ee ff` = Checksum/terminator


### USB Permissions

Create udev rule for non-root access or run script with sudo.


### Basic Usage

```python
#!/usr/bin/env python3
from dl24p_controller import DL24P

# Create controller
dl24 = DL24P()

# Connect and initialize
if dl24.connect() and dl24.initialize():
    
    # Set voltage cutoff to 3.0V
    dl24.set_voltage_cutoff(3.0)
    
    # Read measurements for 5 seconds
    dl24.read_measurements(duration=5)
    
    # Disconnect
    dl24.disconnect()
```

### Command Line Test

```bash
# Run the main controller (includes examples)
python3 dl24p_controller.py

# Run voltage cutoff test
python3 test_voltage_cutoff.py
```


### DL24P Class Methods

#### Connection
- `connect()` - Connect to device via USB
- `initialize()` - Initialize device and start data stream
- `disconnect()` - Clean disconnect

#### Reading Data
- `read_packet(timeout=2000)` - Read raw packet from device
- `parse_packet(data)` - Parse packet into measurements
- `read_measurements(duration=5)` - Read and display measurements

#### Writing Settings
- `write_register(register, value)` - Write float value to register
- `set_voltage_cutoff(voltage)` - Set voltage cutoff (V)
- `set_current(current)` - Set load current (A)

#### Maintenance
- `keep_alive()` - Send keep-alive to maintain connection

### Known Registers

| Register | Function | Value Type |
|----------|----------|------------|
| `0x21` | Set Current | Float (big-endian) |
| `0x29` | Voltage Cutoff | Float (big-endian) |


### Read Commands (Host to Device)

**Mode Switch (Initialize):**
```
55 05 01 05 00 00 00 00 ee ff
```

**Request Config:**
```
55 05 01 03 00 00 00 00 ee ff
```

**Request Live Data:**
```
55 05 01 05 00 00 00 00 ee ff
```

### Write Commands (Host → Device)

**Generic Write:**
```
55 05 01 [REG] [VAL_BYTE1] [VAL_BYTE2] [VAL_BYTE3] [VAL_BYTE4] 00 00 00 ee ff [zeros...]
```
- Total packet size: 91 bytes
- Value: 4-byte **big-endian** float

**Set Voltage Cutoff Examples:**

2.0V:
```
55 05 01 29 40 00 00 00 ee ff 00 00 00 ...
```

5.0V:
```
55 05 01 29 40 a0 00 00 ee ff 00 00 00 ...
```

10.0V:
```
55 05 01 29 41 20 00 00 ee ff 00 00 00 ...
```

### Response Packets (Device → Host)

**Live Data Response (aa 05 01 05):**
- Bytes 8-11: Voltage (uint32, little-endian, /1000)
- Bytes 12-15: Current (uint32, little-endian, /1000)
- Bytes 16-19: Power (uint32, little-endian, /1000)
- Bytes 20-23: Energy (uint32, little-endian, /100)
- Bytes 28-31: Amp-hours (uint32, little-endian, /1000)
- Bytes 36-39: Temperature (uint32, little-endian, /1000)

**Config Response (aa 05 01 03):**
- Floats in big-endian format
- Index 0: Set current
- Index 4: Cutoff voltage

## 🔍 Discovery Process

The write protocol was reverse engineered using:

1. **Wireshark USB capture** on Windows while using official app
2. **Pattern analysis** of packets during voltage changes
3. **Float encoding detection** - discovered big-endian format
4. **Command structure mapping** from captured packets

Key findings:
- Write commands use command byte `01`
- Values are encoded as **big-endian floats** (different from read responses!)
- Register `0x29` controls voltage cutoff
- Packet must be padded to 91 bytes

## 📝 Example Scripts

### Set Voltage and Monitor

```python
from dl24p_controller import DL24P
import time

dl24 = DL24P()
if dl24.connect() and dl24.initialize():
    # Set low cutoff for testing
    dl24.set_voltage_cutoff(2.0)
    print("Monitoring with 2.0V cutoff...")
    dl24.read_measurements(duration=10)
    
    # Raise cutoff
    dl24.set_voltage_cutoff(5.0)
    print("Now monitoring with 5.0V cutoff...")
    dl24.read_measurements(duration=10)
    
    dl24.disconnect()
```

### Set Current and Test Load

```python
from dl24p_controller import DL24P
import time

dl24 = DL24P()
if dl24.connect() and dl24.initialize():
    # Test different current levels
    for current in [1.0, 2.0, 3.0, 5.0]:
        print(f"\nTesting {current}A load...")
        dl24.set_current(current)
        time.sleep(1)
        dl24.read_measurements(duration=5)
    
    dl24.disconnect()
```

### Battery Discharge Cycle

```python
from dl24p_controller import DL24P
import time

dl24 = DL24P()
if dl24.connect() and dl24.initialize():
    # Set discharge parameters
    dl24.set_voltage_cutoff(3.0)  # Stop at 3.0V
    dl24.set_current(2.0)          # 2A discharge
    
    print("Starting battery discharge cycle...")
    print("Will stop when voltage reaches 3.0V")
    
    # Monitor until cutoff
    start_time = time.time()
    while True:
        data = dl24.read_packet()
        if data:
            parsed = dl24.parse_packet(data)
            if parsed and parsed.get('voltage'):
                v = parsed['voltage']
                i = parsed['current']
                print(f"{time.time()-start_time:.0f}s: {v:.3f}V, {i:.3f}A")
                
                if v < 3.1:  # Close to cutoff
                    print("⚠️  Approaching cutoff voltage!")
                    break
        
        time.sleep(1)
    
    dl24.disconnect()
```

### Sweep Voltages

```python
from dl24p_controller import DL24P
import time

dl24 = DL24P()
if dl24.connect() and dl24.initialize():
    voltages = [2.0, 3.0, 4.0, 5.0]
    
    for v in voltages:
        print(f"\n=== Testing {v}V cutoff ===")
        dl24.set_voltage_cutoff(v)
        time.sleep(1)
        dl24.read_measurements(duration=3)
    
    dl24.disconnect()
```
### Plotting
```bash
# Create a live plot of CC mode measurements from DL24P
# Example with 3.0 V cutoff and 2.0 A CC

python3 battery_cycler_plot.py --cutoff 3.0 --current 2.0 --output filename.csv



## Troubleshooting

### Device Not Found
```bash
# Check if device is detected
lsusb | grep 0483:5750

# Check permissions
ls -l /dev/bus/usb/*/***  # find your device
```

### Permission Denied
- Make sure udev rules are installed
- Try with sudo temporarily to verify it's a permissions issue
- Unplug and replug device after adding udev rules

### No Response from Device
- Device might be in wrong mode - try power cycling it
- Check if another program is using it: `lsof | grep usb`
- Try increasing timeouts in the code

### Write Not Working
- Verify device initialized successfully
- Check that keep-alive is running
- Try writing after reading some data first

## Next Steps

### Registers to Discover
~~- Set current limit~~ (Completed)
- Set power limit  
~~- Enable/disable load~~ (Completed)
- Timer settings
- Protection settings

### Methods
1. Capture more Wireshark traces while changing different settings using Windows software
2. Look for byte-change patterns in write commands
3. Test discovered register addresses through write commands

## 📖 References

- [improwis DL24 Blog](https://www.improwis.com/projects/sw_dl24/) - Original BLE protocol
- [Flaviu Tamas DL24M Reversing](https://flaviutamas.com/2022/dl24m-reversing) - BLE analysis
- This project - USB HID protocol reverse engineering

## 📄 License

This is a reverse engineering project for educational and personal use.


**Happy load testing!**
