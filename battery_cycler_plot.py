#!/usr/bin/env python3
"""
DL24P Battery Cycler with Live Plotting

Real-time graphical discharge monitoring with data logging.
"""
import sys
import time
import csv
import argparse
from datetime import datetime
from dl24p_controller import DL24P

# Check for matplotlib
try:
    import matplotlib
    # Set backend before importing pyplot to prevent focus stealing
    matplotlib.use('TkAgg')  # Use TkAgg backend which doesn't steal focus
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("⚠️  matplotlib not found - live plotting disabled")
    print("   Install with: pip install matplotlib --break-system-packages")


class BatteryCyclerWithPlot:
    """Automated battery discharge cycler with live plotting"""
    
    def __init__(self, cutoff_voltage, discharge_current, 
                 log_interval=1.0, output_file=None, temp_warning=50.0,
                 enable_plot=True):
        """
        Initialize battery cycler with plotting
        
        Args:
            cutoff_voltage: Voltage to stop discharge (V)
            discharge_current: Discharge current (A)
            log_interval: Seconds between data points (default 1.0)
            output_file: CSV filename for data logging
            temp_warning: Temperature warning threshold (°C)
            enable_plot: Enable live plotting (requires matplotlib)
        """
        self.cutoff_voltage = cutoff_voltage
        self.discharge_current = discharge_current
        self.log_interval = log_interval
        self.output_file = output_file
        self.temp_warning = temp_warning
        self.enable_plot = enable_plot and HAS_MATPLOTLIB
        
        self.dl24 = DL24P()
        self.start_time = None
        self.data_points = []
        self.running = False
        
        # Plotting setup
        if self.enable_plot:
            self.setup_plots()
        
    def setup_plots(self):
        """Setup matplotlib live plots"""
        plt.style.use('dark_background')
        self.fig, self.axs = plt.subplots(2, 2, figsize=(12, 8))
        self.fig.suptitle('Battery Discharge Monitor', fontsize=16, fontweight='bold')
        
        # Try to configure window to not steal focus (platform-dependent)
        try:
            # For Tk backend
            if hasattr(self.fig.canvas.manager, 'window'):
                self.fig.canvas.manager.window.attributes('-topmost', False)
        except:
            pass  # Silently ignore if not supported
        
        # Plot 1: Voltage vs Time
        self.ax_voltage = self.axs[0, 0]
        self.ax_voltage.set_title('Voltage')
        self.ax_voltage.set_xlabel('Time (minutes)')
        self.ax_voltage.set_ylabel('Voltage (V)')
        self.ax_voltage.grid(True, alpha=0.3)
        self.line_voltage, = self.ax_voltage.plot([], [], 'c-', linewidth=2)
        
        # Plot 2: Current vs Time
        self.ax_current = self.axs[0, 1]
        self.ax_current.set_title('Current')
        self.ax_current.set_xlabel('Time (minutes)')
        self.ax_current.set_ylabel('Current (A)')
        self.ax_current.grid(True, alpha=0.3)
        self.line_current, = self.ax_current.plot([], [], 'y-', linewidth=2)
        
        # Plot 3: Power vs Time
        self.ax_power = self.axs[1, 0]
        self.ax_power.set_title('Power')
        self.ax_power.set_xlabel('Time (minutes)')
        self.ax_power.set_ylabel('Power (W)')
        self.ax_power.grid(True, alpha=0.3)
        self.line_power, = self.ax_power.plot([], [], 'm-', linewidth=2)
        
        # Plot 4: Temperature vs Time
        self.ax_temp = self.axs[1, 1]
        self.ax_temp.set_title('Temperature')
        self.ax_temp.set_xlabel('Time (minutes)')
        self.ax_temp.set_ylabel('Temperature (°C)')
        self.ax_temp.grid(True, alpha=0.3)
        self.line_temp, = self.ax_temp.plot([], [], 'r-', linewidth=2)
        
        # Add cutoff voltage line
        self.cutoff_line = self.ax_voltage.axhline(
            y=self.cutoff_voltage, 
            color='r', 
            linestyle='--', 
            linewidth=2,
            label=f'Cutoff ({self.cutoff_voltage}V)'
        )
        self.ax_voltage.legend()
        
        # Add temp warning line
        self.temp_warning_line = self.ax_temp.axhline(
            y=self.temp_warning,
            color='orange',
            linestyle='--',
            linewidth=2,
            label=f'Warning ({self.temp_warning}°C)'
        )
        self.ax_temp.legend()
        
        plt.tight_layout()
        
    def update_plots(self):
        """Update all plots with current data"""
        if not self.enable_plot or not self.data_points:
            return
        
        # Extract data
        times = [p['elapsed_seconds'] / 60.0 for p in self.data_points]  # Convert to minutes
        voltages = [p['voltage'] for p in self.data_points]
        currents = [p['current'] for p in self.data_points]
        powers = [p['power'] for p in self.data_points]
        temps = [p['temperature'] for p in self.data_points]
        
        # Update voltage plot
        self.line_voltage.set_data(times, voltages)
        self.ax_voltage.relim()
        self.ax_voltage.autoscale_view()
        
        # Update current plot
        self.line_current.set_data(times, currents)
        self.ax_current.relim()
        self.ax_current.autoscale_view()
        
        # Update power plot
        self.line_power.set_data(times, powers)
        self.ax_power.relim()
        self.ax_power.autoscale_view()
        
        # Update temperature plot
        self.line_temp.set_data(times, temps)
        self.ax_temp.relim()
        self.ax_temp.autoscale_view()
        
        # Add statistics text
        if len(self.data_points) > 0:
            last = self.data_points[-1]
            stats_text = (
                f"Time: {last['elapsed_seconds']/60:.1f}min | "
                f"V: {last['voltage']:.3f}V | "
                f"I: {last['current']:.3f}A | "
                f"P: {last['power']:.2f}W | "
                f"E: {last['energy_wh']:.2f}Wh | "
                f"Q: {last['capacity_ah']:.3f}Ah"
            )
            self.fig.suptitle(f'Battery Discharge Monitor\n{stats_text}', 
                            fontsize=12, fontweight='bold')
        
        # Draw without blocking or stealing focus
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
    
    def setup(self):
        """Connect and configure device"""
        print("="*70)
        print("DL24P Battery Cycler with Live Plotting")
        print("="*70)
        print()
        print(f"Configuration:")
        print(f"  Cutoff Voltage:    {self.cutoff_voltage}V")
        print(f"  Discharge Current: {self.discharge_current}A")
        print(f"  Log Interval:      {self.log_interval}s")
        print(f"  Output File:       {self.output_file or 'None (display only)'}")
        print(f"  Temp Warning:      {self.temp_warning}°C")
        print(f"  Live Plotting:     {'Enabled' if self.enable_plot else 'Disabled'}")
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
        if self.enable_plot:
            print("⚠️  Live plotting enabled - graphs will open in new window")
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
        self.running = True
        
        # Show plots if enabled
        if self.enable_plot:
            plt.ion()
            plt.show()
        
        return True
    
    def log_data_point(self, parsed_data):
        """Log a single data point"""
        if not parsed_data or parsed_data.get('format') != 'live_data':
            return None
        
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
              f"Q: {data_point['capacity_ah']:6.3f}mAh | "
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
        last_plot_update = time.time()
        
        try:
            while self.running:
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
                                self.running = False
                                break
                    
                    # Update plots every 0.5 seconds
                    if self.enable_plot and time.time() - last_plot_update >= 0.5:
                        self.update_plots()
                        last_plot_update = time.time()
                
                # Send keep-alive
                self.dl24.keep_alive()
                
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            print()
            print()
            print("="*70)
            print("⚠️  Discharge interrupted by user")
            print("="*70)
            self.running = False
        
        # Turn off load
        print()
        print("Disabling load...")
        self.dl24.load_off()
        time.sleep(0.5)
        print("✓ Load disabled")
        
        # Keep plots open
        if self.enable_plot and self.data_points:
            print()
            print("📊 Plots are still open - close the window when done viewing")
            self.update_plots()
            plt.ioff()
            plt.show()  # Block here until user closes window
    
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
        print(f"Total Capacity:      {total_capacity:.3f}Ah ({total_capacity*1000:.0f}mAh)")
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
        description='DL24P Battery Discharge Cycler with Live Plotting',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic discharge with live plots
  python3 battery_cycler_plot.py --cutoff 3.0 --current 2.0
  
  # With data logging
  python3 battery_cycler_plot.py --cutoff 3.0 --current 2.0 --output test.csv
  
  # Disable plots (if matplotlib not available)
  python3 battery_cycler_plot.py --cutoff 3.0 --current 2.0 --no-plot
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
    parser.add_argument('--no-plot', action='store_true',
                       help='Disable live plotting')
    
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
    cycler = BatteryCyclerWithPlot(
        cutoff_voltage=args.cutoff,
        discharge_current=args.current,
        log_interval=args.interval,
        output_file=args.output,
        temp_warning=args.temp_warning,
        enable_plot=not args.no_plot
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
