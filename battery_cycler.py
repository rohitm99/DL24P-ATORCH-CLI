#!/usr/bin/env python3
"""
DL24P Battery Cycler - Automated Discharge Testing

Complete battery discharge automation with data logging and safety features.
"""
import sys
import time
import csv
import argparse
from datetime import datetime
from dl24p_controller import DL24P

class BatteryCycler:
    """Automated battery discharge cycler"""
    
    def __init__(self, cutoff_voltage, discharge_current, 
                 log_interval=1.0, output_file=None, temp_warning=50.0):
        """
        Initialize battery cycler
        
        Args:
            cutoff_voltage: Voltage to stop discharge (V)
            discharge_current: Discharge current (A)
            log_interval: Seconds between data points (default 1.0)
            output_file: CSV filename for data logging
            temp_warning: Temperature warning threshold (°C)
        """
        self.cutoff_voltage = cutoff_voltage
        self.discharge_current = discharge_current
        self.log_interval = log_interval
        self.output_file = output_file
        self.temp_warning = temp_warning
        
        self.dl24 = DL24P()
        self.start_time = None
        self.data_points = []
        
    def setup(self):
        """Connect and configure device"""
        print("="*70)
        print("DL24P Battery Cycler")
        print("="*70)
        print()
        print(f"Configuration:")
        print(f"  Cutoff Voltage:    {self.cutoff_voltage}V")
        print(f"  Discharge Current: {self.discharge_current}A")
        print(f"  Log Interval:      {self.log_interval}s")
        print(f"  Output File:       {self.output_file or 'None (display only)'}")
        print(f"  Temp Warning:      {self.temp_warning}°C")
        print()
        
        # Connect
        print("Connecting to DL24P...")
        if not self.dl24.connect():
            print("❌ Failed to connect to device!")
            return False
        
        # Initialize
        if not self.dl24.initialize():
            print("❌ Failed to initialize device!")
            return False
        
        print("✓ Device connected and initialized")
        print()
        
        # Configure device
        print("Configuring device...")
        
        # Set voltage cutoff
        if not self.dl24.set_voltage_cutoff(self.cutoff_voltage):
            print("❌ Failed to set voltage cutoff!")
            return False
        
        # Set discharge current
        if not self.dl24.set_current(self.discharge_current):
            print("❌ Failed to set discharge current!")
            return False
        
        # Make sure load is off initially
        self.dl24.load_off()
        time.sleep(0.5)
        
        print("✓ Device configured")
        print()
        
        return True
    
    def start_discharge(self):
        """Start the discharge cycle"""
        print("="*70)
        print("Starting Discharge Cycle")
        print("="*70)
        print()
        
        # Get initial voltage
        print("Checking initial voltage...")
        for _ in range(3):
            data = self.dl24.read_packet()
            if data:
                parsed = self.dl24.parse_packet(data)
                if parsed and parsed.get('voltage'):
                    initial_voltage = parsed['voltage']
                    print(f"Initial voltage: {initial_voltage:.3f}V")
                    
                    if initial_voltage < self.cutoff_voltage + 0.1:
                        print(f"⚠️  WARNING: Initial voltage ({initial_voltage:.3f}V) is too close to cutoff ({self.cutoff_voltage}V)!")
                        response = input("Continue anyway? (yes/no): ")
                        if response.lower() != 'yes':
                            return False
                    break
            time.sleep(0.2)
        
        print()
        input("⚠️  Ready to start discharge. Press ENTER to begin...")
        print()
        
        # Turn on load
        print("Enabling load...")
        if not self.dl24.load_on():
            print("❌ Failed to enable load!")
            return False
        
        print("✓ Load enabled - discharge started!")
        print()
        
        self.start_time = time.time()
        return True
    
    def log_data_point(self, parsed_data):
        """Log a single data point"""
        if not parsed_data or parsed_data.get('format') != 'live_data':
            return
        
        elapsed = time.time() - self.start_time
        
        data_point = {
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': elapsed,
            'voltage': parsed_data['voltage'],
            'current': parsed_data['current'],
            'power': parsed_data['power'],
            'energy_wh': parsed_data['energy'],
            'capacity_ah': parsed_data['amphours'],
            'temperature': parsed_data['temperature']
        }
        
        self.data_points.append(data_point)
        
        # Display
        print(f"{elapsed:7.1f}s | "
              f"V: {data_point['voltage']:6.3f}V | "
              f"I: {data_point['current']:6.3f}A | "
              f"P: {data_point['power']:6.2f}W | "
              f"E: {data_point['energy_wh']:7.2f}Wh | "
              f"Q: {data_point['capacity_ah']:6.3f}Ah | "
              f"T: {data_point['temperature']:5.1f}°C")
        
        # Temperature warning
        if data_point['temperature'] > self.temp_warning:
            print(f"⚠️  HIGH TEMPERATURE WARNING: {data_point['temperature']:.1f}°C!")
        
        # Voltage warning
        if data_point['voltage'] < self.cutoff_voltage + 0.2:
            print(f"⚠️  Approaching cutoff voltage!")
        
        return data_point
    
    def run_discharge(self):
        """Run the discharge cycle until cutoff"""
        print("="*70)
        print("Discharge Progress")
        print("="*70)
        print()
        print("   Time   | Voltage | Current |  Power  |  Energy  | Capacity |  Temp  ")
        print("-"*70)
        
        last_log_time = time.time()
        
        try:
            while True:
                # Read data
                data = self.dl24.read_packet(timeout=500)
                if data:
                    parsed = self.dl24.parse_packet(data)
                    
                    # Log at specified interval
                    if time.time() - last_log_time >= self.log_interval:
                        data_point = self.log_data_point(parsed)
                        last_log_time = time.time()
                        
                        if data_point:
                            # Check cutoff
                            if data_point['voltage'] <= self.cutoff_voltage:
                                print()
                                print("="*70)
                                print(f"✓ CUTOFF VOLTAGE REACHED: {data_point['voltage']:.3f}V")
                                print("="*70)
                                break
                
                # Send keep-alive every 0.5s
                if time.time() - self.start_time > 0.5:
                    self.dl24.keep_alive()
                
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            print()
            print()
            print("="*70)
            print("⚠️  Discharge interrupted by user")
            print("="*70)
        
        # Turn off load
        print()
        print("Disabling load...")
        self.dl24.load_off()
        time.sleep(0.5)
        print("✓ Load disabled")
    
    def save_results(self):
        """Save results to CSV"""
        if not self.output_file or not self.data_points:
            return
        
        print()
        print(f"Saving data to {self.output_file}...")
        
        try:
            with open(self.output_file, 'w', newline='') as f:
                fieldnames = ['timestamp', 'elapsed_seconds', 'voltage', 'current', 
                            'power', 'energy_wh', 'capacity_ah', 'temperature']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                writer.writeheader()
                for point in self.data_points:
                    writer.writerow(point)
            
            print(f"✓ Saved {len(self.data_points)} data points")
        except Exception as e:
            print(f"❌ Failed to save data: {e}")
    
    def print_summary(self):
        """Print discharge summary statistics"""
        if not self.data_points:
            return
        
        print()
        print("="*70)
        print("Discharge Summary")
        print("="*70)
        print()
        
        first = self.data_points[0]
        last = self.data_points[-1]
        
        total_time = last['elapsed_seconds']
        total_energy = last['energy_wh']
        total_capacity = last['capacity_ah']
        
        # Calculate averages
        avg_voltage = sum(p['voltage'] for p in self.data_points) / len(self.data_points)
        avg_current = sum(p['current'] for p in self.data_points) / len(self.data_points)
        avg_power = sum(p['power'] for p in self.data_points) / len(self.data_points)
        max_temp = max(p['temperature'] for p in self.data_points)
        
        print(f"Test Duration:       {total_time/3600:.2f} hours ({total_time:.0f} seconds)")
        print(f"Initial Voltage:     {first['voltage']:.3f}V")
        print(f"Final Voltage:       {last['voltage']:.3f}V")
        print(f"Voltage Drop:        {first['voltage'] - last['voltage']:.3f}V")
        print()
        print(f"Total Energy:        {total_energy:.2f}Wh")
        print(f"Total Capacity:      {total_capacity:.3f}Ah")
        print()
        print(f"Average Voltage:     {avg_voltage:.3f}V")
        print(f"Average Current:     {avg_current:.3f}A")
        print(f"Average Power:       {avg_power:.2f}W")
        print()
        print(f"Peak Temperature:    {max_temp:.1f}°C")
        print(f"Data Points:         {len(self.data_points)}")
        print()
        
        if self.output_file:
            print(f"Data saved to:       {self.output_file}")
        
        print("="*70)
    
    def cleanup(self):
        """Clean up and disconnect"""
        print()
        print("Disconnecting...")
        self.dl24.disconnect()


def main():
    parser = argparse.ArgumentParser(
        description='DL24P Battery Discharge Cycler',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic discharge to 3.0V at 2A
  python3 battery_cycler.py --cutoff 3.0 --current 2.0
  
  # With data logging every 5 seconds
  python3 battery_cycler.py --cutoff 3.0 --current 2.0 --interval 5 --output battery_test.csv
  
  # Li-ion discharge with custom temp warning
  python3 battery_cycler.py --cutoff 3.0 --current 1.0 --temp-warning 45 --output liion_test.csv
        """
    )
    
    parser.add_argument('--cutoff', type=float, required=True,
                       help='Cutoff voltage in volts (e.g., 3.0)')
    parser.add_argument('--current', type=float, required=True,
                       help='Discharge current in amps (e.g., 2.0)')
    parser.add_argument('--interval', type=float, default=1.0,
                       help='Data logging interval in seconds (default: 1.0)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output CSV filename (default: display only)')
    parser.add_argument('--temp-warning', type=float, default=50.0,
                       help='Temperature warning threshold in °C (default: 50.0)')
    
    args = parser.parse_args()
    
    # Validation
    if args.cutoff < 0 or args.cutoff > 30:
        print("❌ Cutoff voltage must be between 0 and 30V")
        sys.exit(1)
    
    if args.current < 0 or args.current > 24:
        print("❌ Current must be between 0 and 24A")
        sys.exit(1)
    
    if args.interval < 0.1:
        print("❌ Interval must be at least 0.1 seconds")
        sys.exit(1)
    
    # Create cycler
    cycler = BatteryCycler(
        cutoff_voltage=args.cutoff,
        discharge_current=args.current,
        log_interval=args.interval,
        output_file=args.output,
        temp_warning=args.temp_warning
    )
    
    # Run discharge cycle
    try:
        if not cycler.setup():
            sys.exit(1)
        
        if not cycler.start_discharge():
            cycler.cleanup()
            sys.exit(1)
        
        cycler.run_discharge()
        cycler.save_results()
        cycler.print_summary()
        cycler.cleanup()
        
        print()
        print("✓ Battery cycle complete!")
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        cycler.cleanup()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        cycler.cleanup()
        sys.exit(1)


if __name__ == '__main__':
    main()
