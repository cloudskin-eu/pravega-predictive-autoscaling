"""
Trace File Processor for Pravega Autoscaler and Workload Generator

This script replays numerical values from a trace file, applying them either to
the Pravega autoscaler (to change segment store replicas) or to a workload
generator (to simulate workload intensity). The replay is time-scaled and can
optionally include delays to mimic real-time progression.
"""

import time
import threading

from src.pravega_autoscaler import PravegaTraceBasedAutoscaler
from src.workload_executors import VideoWorkloadGenerator


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
    time_unit_multiplier = {
        'seconds': 1,
        'minutes': 60,
        'hours': 3600
    }

    unit_multiplier = time_unit_multiplier.get(time_unit.lower(), 60)  # Default to minutes if unit not recognized

    with open(file_path, 'r') as file:
        sleep_interval = unit_multiplier / replay_speed
        for line in file:
            try:
                value = float(line.strip())  # Assuming each line contains a numerical value
                print(f"Parsed trace value: {value}, now processing and wait for {sleep_interval} seconds.")
                processing_callback(value)
                if do_sleep:
                    time.sleep(sleep_interval)
            except ValueError:
                print(f"Skipping line: {line.strip()}, not a valid numerical value")


if __name__ == "__main__":
    """
    Main entry point: starts two parallel threads.

    - One runs the Pravega autoscaler in advance of the workload trace.
    - Another replays the trace for the workload generator.
    - Both threads join before exiting.

    This simulates a realistic environment where scaling occurs slightly ahead
    of actual workload changes.
    """
    # Amount of time that the autoscaler will be in advance to the workload trace.
    time_ahead = 10
    pravega_autoscaler = threading.Thread(target=process_trace_file, args=("../resources/test.csv",
                                                                           PravegaTraceBasedAutoscaler('default').run,
                                                                           'minutes', 2, True))
    pravega_autoscaler.start()
    time.sleep(time_ahead)
    workload_generator = threading.Thread(target=process_trace_file, args=("../resources/test.csv",
                                                                  VideoWorkloadGenerator('default').run,
                                                                  'minutes', 2, True))
    workload_generator.start()
    workload_generator.join()
    pravega_autoscaler.join()
    print("Main thread exiting")
