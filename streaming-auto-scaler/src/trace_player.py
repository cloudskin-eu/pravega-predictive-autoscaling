"""
Trace File Processor for Pravega Autoscaler and Workload Generator
This script replays numerical values from a trace file, applying them either to
the Pravega autoscaler (to change segment store replicas) or to a workload
generator (to simulate workload intensity). The replay is time-scaled and can
optionally include delays to mimic real-time progression.
"""
import time
import threading
from datetime import datetime
from pravega_autoscaler import PravegaTraceBasedAutoscaler
from workload_executors import VideoWorkloadGenerator

def log_with_time(message):
    """Helper function to log messages with timestamps."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] TracePlayer - {message}")

def process_trace_file_with_range(file_path, processing_callback, start_line=0, end_line=None, time_unit='minutes', replay_speed=20, do_sleep=False):
    """
    Replay values from a trace file within a specific range and pass them to a processing callback.
    
    Args:
        file_path (str): Path to the trace file. Each line should contain a numeric value.
        processing_callback (Callable): Function to process each parsed value.
        start_line (int): Starting line index (inclusive). Defaults to 0.
        end_line (int): Ending line index (exclusive). None means process till end of file.
        time_unit (str, optional): Time unit in the trace file ('seconds', 'minutes', or 'hours').
                                   Defaults to 'minutes'.
        replay_speed (int, optional): Factor to speed up or slow down replay.
                                      Higher values = faster replay. Defaults to 20.
        do_sleep (bool, optional): If True, sleep between trace values to simulate passage of time.
                                   Defaults to False.
    Behavior:
        - Reads the trace file line by line.
        - Skips lines until start_line
        - Stops processing after end_line
        - Parses each line as a float value.
        - Invokes the callback with the parsed value.
        - Optionally sleeps between iterations to simulate real-time behavior.
    Logs:
        Prints the parsed values and sleep intervals, or skips invalid lines with timestamps.
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

    total_elapsed_virtual_time = 0  # Track cumulative virtual time passed in simulation
    processed_count = 0  # Track how many lines we've actually processed
    
    # Process the trace file
    with open(file_path, 'r') as file:
        for idx, line in enumerate(file):
            # Skip lines before start_line
            if idx < start_line:
                continue
                
            # Stop if we've reached end_line
            if end_line is not None and idx >= end_line:
                break
                
            try:
                value = float(line.strip())
                log_with_time(f"Parsed trace value at original index {idx}, processed index {processed_count}: {value}. Now processing...")
                processing_callback(value)

                if do_sleep:
                    log_with_time(f"Waiting/Sleep interval for {sleep_interval:.2f} seconds.")
                    time.sleep(sleep_interval)
                
                total_elapsed_virtual_time += unit_multiplier
                log_with_time(f"Simulated elapsed time so far: {total_elapsed_virtual_time} {time_unit}")
                processed_count += 1
                    
            except ValueError:
                log_with_time(f"Skipping line: '{line.strip()}', not a valid numerical value.")

def process_trace_file(file_path, processing_callback, time_unit='minutes', replay_speed=20, do_sleep=False):
    """
    Replay start and end from a trace file and pass them to a processing callback.
    """
    return process_trace_file_with_range(file_path, processing_callback, 0, None, time_unit, replay_speed, do_sleep)

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
    NCT_TRACE = "streaming-auto-scaler/resources/nct.csv"
    LSTM_TRACE = "streaming-auto-scaler/results/predictive_lstm_20ms_95p_20min_num_segment_stores.csv" 
    REACTIVE_TRACE = "streaming-auto-scaler/results/reactive_vanilla_20ms_95p_20min_num_segment_stores.csv"
    REACTIVE_MEM_TRACE = "streaming-auto-scaler/results/reactive_memory_20ms_95p_20min_num_segment_stores.csv"
    ORACLE_TRACE = "streaming-auto-scaler/results/predictive_oracle_20ms_95p_20min_num_segment_stores.csv"

    time_ahead = 50 
    replay_speed = 15 # 1 week in about 12 hours
    
    START_LINE = 10080
    END_LINE = 20160

    log_with_time("Starting Pravega Autoscaler thread...")
    pravega_autoscaler = threading.Thread(
        target=process_trace_file, 
        args=(
            LSTM_TRACE,
            PravegaTraceBasedAutoscaler('default').run,
            'minutes', 
            replay_speed, 
            True
        )
    )
    pravega_autoscaler.start()
    
    # Wait before starting workload generator
    log_with_time(f"Waiting {time_ahead} seconds before starting workload generator...")
    time.sleep(time_ahead)
    
    log_with_time("Starting Workload Generator thread (processing lines {} to {})...".format(START_LINE, END_LINE))
    workload_generator = threading.Thread(
        target=process_trace_file_with_range, 
        args=(
            NCT_TRACE,
            VideoWorkloadGenerator('default').run,
            START_LINE,
            END_LINE,
            'minutes', 
            replay_speed, 
            True
        )
    )
    workload_generator.start()

    workload_generator.join()
    pravega_autoscaler.join()
    
    log_with_time("Main thread exiting")

if __name__ == "__main__":
    main()