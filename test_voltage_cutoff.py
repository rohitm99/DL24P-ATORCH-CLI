#!/usr/bin/env python3
"""
Simple test script to set voltage cutoff on DL24P
"""
import sys
import time

# Import the controller (assuming dl24p_controller.py is in same directory)
from dl24p_controller import DL24P

def test_voltage_cutoff():
    """Test setting voltage cutoff"""
    
    print("="*60)
    print("DL24P Voltage Cutoff Test")
    print("="*60)
    
    # Connect
    dl24 = DL24P()
    if not dl24.connect():
        print("Failed to connect!")
        return False
    
    # Initialize
    if not dl24.initialize():
        print("Failed to initialize!")
        return False
    
    # Test different voltage cutoffs
    test_voltages = [2.0, 3.0, 5.0, 10.0, 2.5]
    
    for voltage in test_voltages:
        print(f"\n{'='*60}")
        print(f"Setting cutoff to {voltage}V")
        print(f"{'='*60}")
        
        if dl24.set_voltage_cutoff(voltage):
            print(f"✓ Successfully set to {voltage}V")
            
            # Read a few measurements to verify
            print("\nVerifying with measurements:")
            dl24.read_measurements(duration=2)
            
            time.sleep(1)
        else:
            print(f"❌ Failed to set {voltage}V")
            break
    
    # Cleanup
    dl24.disconnect()
    print("\n✓ Test complete!")
    return True


if __name__ == '__main__':
    try:
        success = test_voltage_cutoff()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
