#!/usr/bin/env python3
"""
DL24P Linux Controller - WITH WRITE CAPABILITY
Based on reverse engineering USB captures and existing working code
"""
import usb.core
import usb.util
import time
import sys
import struct

class DL24P:
    """Controller for ATORCH DL24P electronic load"""
    
    VENDOR_ID = 0x0483
    PRODUCT_ID = 0x5750
    EP_IN = 0x81
    EP_OUT = 0x01
    
    # Read commands (from working code)
    MODE_SWITCH_CMD = [0x55, 0x05, 0x01, 0x05, 0x00, 0x00, 0x00, 0x00, 0xee, 0xff]
    CONFIG_REQUEST_CMD = [0x55, 0x05, 0x01, 0x03, 0x00, 0x00, 0x00, 0x00, 0xee, 0xff]
    DATA_REQUEST_CMD = [0x55, 0x05, 0x01, 0x05, 0x00, 0x00, 0x00, 0x00, 0xee, 0xff]
    
    # Register addresses (discovered from Wireshark)
    REG_SET_CURRENT = 0x21     # Set current limit
    REG_LOAD_ENABLE = 0x25     # Load enable/disable (0=off, 1=on)
    REG_VOLTAGE_CUTOFF = 0x29  # Voltage cutoff setting
    
    def __init__(self):
        self.dev = None
        self.initialized = False
        
    def connect(self):
        """Connect to DL24P device"""
        self.dev = usb.core.find(idVendor=self.VENDOR_ID, idProduct=self.PRODUCT_ID)
        
        if self.dev is None:
            print("❌ DL24P not found!")
            print(f"   Looking for: VID={self.VENDOR_ID:04x} PID={self.PRODUCT_ID:04x}")
            return False
        
        print(f"✓ Found DL24P: {self.dev.manufacturer} {self.dev.product}")
        
        # Detach kernel driver if active
        if self.dev.is_kernel_driver_active(0):
            try:
                self.dev.detach_kernel_driver(0)
                print("  Detached kernel driver")
            except Exception as e:
                print(f"  Warning: Could not detach kernel driver: {e}")
        
        try:
            self.dev.set_configuration()
            print("  USB configuration set")
        except Exception as e:
            print(f"  Warning: Could not set configuration: {e}")
        
        return True
    
    def initialize(self):
        """Send initialization sequence to wake up the device"""
        if not self.dev:
            return False
        
        print("\n🔧 Initializing device...")
        
        try:
            # Step 1: Switch to HID mode
            print("  [1/2] Switching to HID mode...")
            self.dev.write(self.EP_OUT, self.MODE_SWITCH_CMD)
            time.sleep(0.5)
            
            # Try to read response
            try:
                response = self.dev.read(self.EP_IN, 64, timeout=1000)
                if response:
                    print(f"        ✓ Mode switch response: {len(response)} bytes")
            except usb.core.USBTimeoutError:
                print(f"        (No immediate response)")
            
            # Step 2: Request live data
            print("  [2/2] Starting data stream...")
            for i in range(3):
                self.dev.write(self.EP_OUT, self.DATA_REQUEST_CMD)
                time.sleep(0.2)
            
            # Verify device is streaming
            try:
                test_data = self.dev.read(self.EP_IN, 64, timeout=2000)
                if test_data:
                    print(f"        ✓ Device streaming! Received {len(test_data)} bytes")
                    self.initialized = True
                    return True
            except usb.core.USBTimeoutError:
                print("        ❌ No response from device")
                return False
                
        except Exception as e:
            print(f"❌ Initialization error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def keep_alive(self):
        """Send keep-alive command to maintain connection"""
        try:
            self.dev.write(self.EP_OUT, self.DATA_REQUEST_CMD)
        except Exception as e:
            print(f"Keep-alive error: {e}")
    
    def read_packet(self, timeout=2000):
        """Read a data packet from the device"""
        try:
            data = self.dev.read(self.EP_IN, 64, timeout=timeout)
            return data.tolist() if data else None
        except usb.core.USBTimeoutError:
            return None
        except Exception as e:
            print(f"Read error: {e}")
            return None
    
    def parse_packet(self, data):
        """Parse packet to extract measurement values"""
        if not data or len(data) < 10:
            return None
        
        try:
            if data[0] == 0xaa and data[1] == 0x05:
                packet_type = data[3]
                
                if packet_type == 0x05:
                    # Live measurement data (integers, little-endian)
                    if len(data) < 44:
                        return None
                    
                    voltage = struct.unpack('<I', bytes(data[8:12]))[0] / 1000.0
                    current = struct.unpack('<I', bytes(data[12:16]))[0] / 1000.0
                    power = struct.unpack('<I', bytes(data[16:20]))[0] / 1000.0
                    energy_wh = struct.unpack('<I', bytes(data[20:24]))[0] / 100.0
                    amphours = struct.unpack('<I', bytes(data[28:32]))[0] / 1000.0
                    temperature = struct.unpack('<I', bytes(data[36:40]))[0] / 1000.0
                    time_counter = struct.unpack('<I', bytes(data[40:44]))[0]
                    
                    return {
                        'format': 'live_data',
                        'voltage': voltage,
                        'current': current,
                        'power': power,
                        'energy': energy_wh,
                        'amphours': amphours,
                        'temperature': temperature,
                        'time_counter': time_counter,
                        'raw': data
                    }
                
                elif packet_type == 0x03:
                    # Configuration data (floats, big-endian)
                    floats = []
                    for i in range(4, min(len(data), 36), 4):
                        try:
                            val = struct.unpack('>f', bytes(data[i:i+4]))[0]
                            floats.append(val)
                        except:
                            floats.append(0.0)
                    
                    return {
                        'format': 'config',
                        'set_current': floats[0] if len(floats) > 0 else 0,
                        'cutoff_voltage': floats[4] if len(floats) > 4 else 0,
                        'all_floats': floats,
                        'raw': data
                    }
            
            return None
            
        except Exception as e:
            print(f"Parse error: {e}")
            return None
    
    def write_register(self, register, value):
        """
        Write a 4-byte float value to a register
        
        Args:
            register: Register address (e.g., 0x29 for voltage cutoff)
            value: Float value to write
        
        Returns:
            bool: True if write appears successful
        """
        if not self.dev or not self.initialized:
            print("❌ Device not initialized!")
            return False
        
        try:
            # Pack value as big-endian float (as discovered in Wireshark)
            value_bytes = struct.pack('>f', value)
            
            # Build write command (91 bytes total to match USB packet size)
            # Format: 55 05 01 [REGISTER] [4-byte-value] 00 00 00 ee ff [pad to 91]
            cmd = [0x55, 0x05, 0x01, register]
            cmd.extend(value_bytes)
            cmd.extend([0x00, 0x00, 0x00, 0xee, 0xff])
            
            # Pad to 91 bytes with zeros
            while len(cmd) < 91:
                cmd.append(0x00)
            
            print(f"📝 Writing register 0x{register:02x} = {value}")
            print(f"   Command: {' '.join(f'{b:02x}' for b in cmd[:20])}...")
            
            # Send the write command
            self.dev.write(self.EP_OUT, cmd)
            time.sleep(0.1)
            
            # Try to read acknowledgment
            try:
                response = self.dev.read(self.EP_IN, 64, timeout=500)
                if response:
                    print(f"   ✓ Device responded: {len(response)} bytes")
                    # Parse response to verify
                    parsed = self.parse_packet(response.tolist())
                    if parsed and parsed.get('format') == 'config':
                        print(f"   ✓ Config updated!")
                        return True
            except usb.core.USBTimeoutError:
                print(f"   (No immediate response)")
            
            return True
            
        except Exception as e:
            print(f"❌ Write error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def write_register_int(self, register, value):
        """
        Write a 4-byte integer value to a register (for boolean/integer registers)
        
        Args:
            register: Register address (e.g., 0x25 for load enable)
            value: Integer value to write (e.g., 0 or 1)
        
        Returns:
            bool: True if write appears successful
        """
        if not self.dev or not self.initialized:
            print("❌ Device not initialized!")
            return False
        
        try:
            # Pack value as big-endian 32-bit integer
            value_bytes = struct.pack('>I', value)
            
            # Build write command
            cmd = [0x55, 0x05, 0x01, register]
            cmd.extend(value_bytes)
            cmd.extend([0x00, 0x00, 0x00, 0xee, 0xff])
            
            # Pad to 91 bytes
            while len(cmd) < 91:
                cmd.append(0x00)
            
            print(f"📝 Writing register 0x{register:02x} = {value} (integer)")
            print(f"   Command: {' '.join(f'{b:02x}' for b in cmd[:20])}...")
            
            # Send the write command
            self.dev.write(self.EP_OUT, cmd)
            time.sleep(0.1)
            
            # Try to read acknowledgment
            try:
                response = self.dev.read(self.EP_IN, 64, timeout=500)
                if response:
                    print(f"   ✓ Device responded: {len(response)} bytes")
            except usb.core.USBTimeoutError:
                print(f"   (No immediate response)")
            
            return True
            
        except Exception as e:
            print(f"❌ Write error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def write_register_int_le(self, register, value):
        """
        Write a 4-byte LITTLE-ENDIAN integer value to a register
        (Used for load enable and other control registers)
        
        Args:
            register: Register address
            value: Integer value to write (e.g., 0 or 1)
        
        Returns:
            bool: True if write appears successful
        """
        if not self.dev or not self.initialized:
            print("❌ Device not initialized!")
            return False
        
        try:
            # Pack value as little-endian 32-bit integer
            value_bytes = struct.pack('<I', value)
            
            # Build write command
            cmd = [0x55, 0x05, 0x01, register]
            cmd.extend(value_bytes)
            cmd.extend([0x00, 0x00, 0x00, 0xee, 0xff])
            
            # Pad to 91 bytes
            while len(cmd) < 91:
                cmd.append(0x00)
            
            print(f"      Writing 0x{register:02x} = {value} (LE int) → {value_bytes.hex(' ')}")
            
            # Send the write command
            self.dev.write(self.EP_OUT, cmd)
            time.sleep(0.05)
            
            # Try to read acknowledgment
            try:
                response = self.dev.read(self.EP_IN, 64, timeout=500)
                if response:
                    print(f"      ✓ Response received")
            except usb.core.USBTimeoutError:
                pass
            
            return True
            
        except Exception as e:
            print(f"❌ Write error: {e}")
            return False
    
    def set_voltage_cutoff(self, voltage):
        """
        Set the voltage cutoff value
        
        Args:
            voltage: Cutoff voltage in volts (e.g., 2.5)
        
        Returns:
            bool: True if successful
        """
        print(f"\n⚡ Setting voltage cutoff to {voltage}V")
        return self.write_register(self.REG_VOLTAGE_CUTOFF, voltage)
    
    def set_current(self, current):
        """
        Set the load current
        
        Args:
            current: Load current in amps (e.g., 3.5)
        
        Returns:
            bool: True if successful
        """
        print(f"\n🔌 Setting load current to {current}A")
        return self.write_register(self.REG_SET_CURRENT, current)
    
    def load_on(self):
        """
        Turn the load ON
        
        Note: This requires a sequence of commands discovered through USB capture
        
        Returns:
            bool: True if successful
        """
        print(f"\n✅ Turning load ON")
        
        try:
            # Step 1: Write to register 0x04 (prerequisite)
            print("   [1/3] Sending prerequisite command to register 0x04...")
            if not self.write_register_int_le(0x04, 0):
                return False
            time.sleep(0.1)
            
            # Step 2: Write to register 0x47 (prerequisite)
            print("   [2/3] Sending prerequisite command to register 0x47...")
            if not self.write_register_int_le(0x47, 0):
                return False
            time.sleep(0.1)
            
            # Step 3: Enable load via register 0x25
            print("   [3/3] Enabling load...")
            if not self.write_register_int_le(self.REG_LOAD_ENABLE, 1):
                return False
            
            print("   ✓ Load ON sequence complete")
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to turn load on: {e}")
            return False
    
    def load_off(self):
        """
        Turn the load OFF
        
        Returns:
            bool: True if successful
        """
        print(f"\n⛔ Turning load OFF")
        return self.write_register_int_le(self.REG_LOAD_ENABLE, 0)
    
    def read_measurements(self, duration=5):
        """
        Read measurements from device for specified duration
        
        Args:
            duration: Time to read in seconds
        """
        print(f"\n📊 Reading measurements for {duration} seconds...")
        print("     Time  | Voltage | Current |  Power  | Energy |  Temp  ")
        print("    -----------------------------------------------------------")
        
        start_time = time.time()
        last_keepalive = start_time
        
        while time.time() - start_time < duration:
            # Send keep-alive every 0.5 seconds
            if time.time() - last_keepalive > 0.5:
                self.keep_alive()
                last_keepalive = time.time()
            
            # Read packet
            data = self.read_packet(timeout=500)
            if data:
                parsed = self.parse_packet(data)
                if parsed and parsed.get('format') == 'live_data':
                    elapsed = time.time() - start_time
                    print(f"    {elapsed:5.1f}s | {parsed['voltage']:6.3f}V | "
                          f"{parsed['current']:6.3f}A | {parsed['power']:6.2f}W | "
                          f"{parsed['energy']:6.2f}Wh | {parsed['temperature']:5.1f}°C")
            
            time.sleep(0.1)
        
        print("\n✓ Measurement complete")
    
    def disconnect(self):
        """Disconnect from device"""
        if self.dev:
            try:
                usb.util.dispose_resources(self.dev)
                print("\n👋 Disconnected from DL24P")
            except:
                pass


def main():
    """Main function with example usage"""
    print("=" * 70)
    print("DL24P Controller - Read & Write Capability")
    print("=" * 70)
    
    # Create controller
    dl24 = DL24P()
    
    # Connect
    if not dl24.connect():
        sys.exit(1)
    
    # Initialize
    if not dl24.initialize():
        print("\n❌ Failed to initialize device")
        sys.exit(1)
    
    print("\n✓ Device ready!")
    
    # Example 1: Read some data
    print("\n" + "="*70)
    print("Example 1: Reading measurements")
    print("="*70)
    dl24.read_measurements(duration=3)
    
    # Example 2: Set voltage cutoff
    print("\n" + "="*70)
    print("Example 2: Setting voltage cutoff")
    print("="*70)
    
    # Set to 3.0V
    if dl24.set_voltage_cutoff(3.0):
        print("✓ Voltage cutoff set to 3.0V")
        time.sleep(1)
        
        # Read to verify
        dl24.read_measurements(duration=2)
        
        # Set back to 2.5V
        dl24.set_voltage_cutoff(2.5)
        print("✓ Voltage cutoff set to 2.5V")
    
    # Example 3: Set current
    print("\n" + "="*70)
    print("Example 3: Setting load current")
    print("="*70)
    
    # Set to 2.0A
    if dl24.set_current(2.0):
        print("✓ Load current set to 2.0A")
        time.sleep(1)
        
        # Read to verify
        dl24.read_measurements(duration=2)
        
        # Set to 5.0A
        dl24.set_current(5.0)
        print("✓ Load current set to 5.0A")
    
    # Example 4: Load control
    print("\n" + "="*70)
    print("Example 4: Load Enable/Disable")
    print("="*70)
    
    # Turn load off
    dl24.load_off()
    print("✓ Load is OFF")
    time.sleep(2)
    
    # Turn load on
    dl24.load_on()
    print("✓ Load is ON")
    time.sleep(1)
    
    # Monitor with load active
    dl24.read_measurements(duration=3)
    
    # Turn load off before disconnect
    dl24.load_off()
    print("✓ Load turned OFF for safety")
    
    # Disconnect
    dl24.disconnect()
    print("\n✓ All done!")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
