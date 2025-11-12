#!/usr/bin/env python3
"""
Test script for DL24P current control
"""
import sys
import time
from dl24p_controller import DL24P

def test_current_control():
    """Test setting load current"""
    
    print("="*70)
    print("DL24P Current Control Test")
    print("="*70)
    
    # Connect
    dl24 = DL24P()
    if not dl24.connect():
        print("❌ Failed to connect!")
        return False
    
    # Initialize
    if not dl24.initialize():
        print("❌ Failed to initialize!")
        return False
    
    # Test different current values
    test_currents = [1.0, 2.0, 3.0, 5.0, 1.5]
    
    for current in test_currents:
        print(f"\n{'='*70}")
        print(f"Setting load current to {current}A")
        print(f"{'='*70}")
        
        if dl24.set_current(current):
            print(f"✓ Successfully set to {current}A")
            
            # Read measurements to verify
            print("\nVerifying with measurements:")
            dl24.read_measurements(duration=3)
            
            time.sleep(1)
        else:
            print(f"❌ Failed to set {current}A")
            break
    
    # Cleanup
    dl24.disconnect()
    print("\n✓ Test complete!")
    return True


def test_combined_control():
    """Test setting both voltage and current"""
    
    print("\n" + "="*70)
    print("DL24P Combined Voltage + Current Control Test")
    print("="*70)
    
    dl24 = DL24P()
    if not dl24.connect() or not dl24.initialize():
        return False
    
    # Test different combinations
    tests = [
        (2.5, 1.0),  # 2.5V cutoff, 1.0A load
        (3.0, 2.0),  # 3.0V cutoff, 2.0A load
        (5.0, 5.0),  # 5.0V cutoff, 5.0A load
        (3.3, 3.0),  # 3.3V cutoff, 3.0A load
    ]
    
    for voltage, current in tests:
        print(f"\n{'='*70}")
        print(f"Setting: {voltage}V cutoff, {current}A load")
        print(f"{'='*70}")
        
        # Set voltage cutoff
        dl24.set_voltage_cutoff(voltage)
        time.sleep(0.5)
        
        # Set current
        dl24.set_current(current)
        time.sleep(0.5)
        
        # Verify
        print("\nVerifying settings:")
        dl24.read_measurements(duration=3)
        
        time.sleep(1)
    
    dl24.disconnect()
    print("\n✓ Combined test complete!")
    return True


if __name__ == '__main__':
    print("\nChoose test:")
    print("  1. Current control only")
    print("  2. Combined voltage + current control")
    print("  3. Both tests")
    print()
    
    choice = input("Enter choice (1-3, default=1): ").strip() or "1"
    
    try:
        if choice == "1":
            test_current_control()
        elif choice == "2":
            test_combined_control()
        elif choice == "3":
            test_current_control()
            time.sleep(2)
            test_combined_control()
        else:
            print("Invalid choice")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
