"""
Trace File Processor for Pravega Autoscaler and Workload Generator

This script replays numerical values from a trace file, applying them either to
the Pravega autoscaler (to change segment store replicas) or to a workload
generator (to simulate workload intensity). The replay is time-scaled and can
optionally include delays to mimic real-time progression.
"""

import time
import threading
from pravega_autoscaler import PravegaTraceBasedAutoscaler
from workload_executors import VideoWorkloadGenerator


def process_trace_file(file_path, processing_callback, time_unit='minutes', replay_speed=20, do_sleep=False):
    """
    Replay values from a trace file and pass them to a processing callback.
    
    Args:
        file_path (str): Path to the trace file. Each line should contain a numeric value.
        processing_callback (Callable): Function to process each parsed value.
        time_unit (str, optional): Time unit in the trace file ('seconds', 'minutes', or 'hours').
                                   Defaults to 'minutes'.
        replay_speed (int, optional): Factor to speed up or slow down replay.
                                      Higher values = faster replay. Defaults to 20.
        do_sleep (bool, optional): If True, sleep between trace values to simulate passage of time.
                                   Defaults to False.

    Behavior:
        - Reads the trace file line by line.
        - Parses each line as a float value.
        - Invokes the callback with the parsed value.
        - Optionally sleeps between iterations to simulate real-time behavior.

    Logs:
        Prints the parsed values and sleep intervals, or skips invalid lines.
    """
    # Define time unit multipliers
    time_unit_multiplier = {
        'seconds': 1,
        'minutes': 60,
        'hours': 3600
    }
    
    # Get the appropriate multiplier or default to minutes
    unit_multiplier = time_unit_multiplier.get(time_unit.lower(), 60)
    
    # Calculate sleep interval based on replay speed
    sleep_interval = unit_multiplier / replay_speed
    
    # Process the trace file
    with open(file_path, 'r') as file:
        for line in file:
            try:
                value = float(line.strip())
                print(f"TracePlayer - Parsed trace value: {value}. Now processing...")
                processing_callback(value)
                
                if do_sleep:
                    print(f"TracePlayer - Waiting/Sleep interval for {sleep_interval} seconds.")
                    time.sleep(sleep_interval)
                    
            except ValueError:
                print(f"TracePlayer - Skipping line: {line.strip()}, not a valid numerical value")

def main():
    """
    Main entry point: starts two parallel threads.
    
    - One runs the Pravega autoscaler in advance of the workload trace.
    - Another replays the trace for the workload generator.
    - Both threads join before exiting.
    
    This simulates a realistic environment where scaling occurs slightly ahead
    of actual workload changes.
    """
    # Configuration
    TRACE_PATH = "/home/ubuntu/autoscaling/pravega-predictive-autoscaling/streaming-auto-scaler/resources/test.csv"
    time_ahead = 20  
    
    pravega_autoscaler = threading.Thread(
        target=process_trace_file, 
        args=(
            TRACE_PATH,
            PravegaTraceBasedAutoscaler('default').run,
            'minutes', 
            2, 
            True
        )
    )
    pravega_autoscaler.start()
    
    # Wait before starting workload generator
    time.sleep(time_ahead)
    
    workload_generator = threading.Thread(
        target=process_trace_file, 
        args=(
            TRACE_PATH,
            VideoWorkloadGenerator('default').run,
            'minutes', 
            2, 
            True
        )
    )
    workload_generator.start()
    workload_generator.join()
    pravega_autoscaler.join()
    
    print("TracePlayer - Main thread exiting")


if __name__ == "__main__":
    main()