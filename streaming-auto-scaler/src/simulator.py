import numpy as np
import os, random
import pandas as pd

# ================================================================
# Global Configuration Parameters
# ================================================================
# These globals configure the simulation of I/O end-to-end latency
# and Pravega auto-scaling policies. They are initialized at runtime.
#
# io_e2e_latency_params: Statistical parameters for latency fitting (unused in this version).
# io_e2e_latency_measurements: Dictionary of empirical latency distributions keyed by writers per instance.
# seconds_per_slot: Simulation slot duration (in seconds).
# FPS: Frames per second per camera (affects number of samples generated).
# last_scaling_latency: Most recent observed latency that triggered a scaling event.
# last_writers_per_instance: Most recent ratio of writers to instances at a scaling event.
# do_next_prediction: Counter controlling when to trigger prediction-based scaling.
# prediction_window: Number of slots considered in predictive scaling.
# cameras_per_surgery: Scaling factor applied to workload trace values.
# trace_to_process: Maximum number of slots from the trace to simulate.
# trace_starting_slot: Index offset in the trace to begin simulation.
# training_starting_slot: Index offset in prediction traces to skip training data.
# latency_percentile: Percentile of latency distribution used for SLA checks.
# latency_threshold: Target latency threshold (in milliseconds).
# latency_tolerance_percentage: Allowed deviation percentage from the latency threshold.
# scaling_latency_penalty_mean: Mean penalty latency introduced by scaling events.
# scaling_latency_penalty_std_dev: Standard deviation of penalty latency for scaling.
# reactive_scaling_with_memory: Flag for memory-aware reactive scaling.
# ================================================================


def distribute_load(total_load, num_parts):
    """
    Evenly distribute a total load across a fixed number of parts.

    Parameters
    ----------
    total_load : int
        The total number of units to distribute.
    num_parts : int
        The number of parts to distribute the load into.

    Returns
    -------
    list[int]
        A list of length `num_parts`, where each element represents
        the load assigned to that part. Any remainder is distributed
        by incrementing the first few parts.
    """
    load_per_part = total_load // num_parts
    remainder = total_load % num_parts
    part_loads = [load_per_part] * num_parts
    for i in range(remainder):
        part_loads[i] += 1
    return part_loads


def io_e2e_latency_modelling(num_writer_reader_pairs, num_pravega_instances, num_samples):
    """
    Model I/O end-to-end latency for a given workload and number of Pravega instances.

    Uses empirical latency distributions (preloaded from CSVs) indexed
    by writers per instance. Random samples are drawn from these
    distributions to synthesize latency values for simulation.

    Parameters
    ----------
    num_writer_reader_pairs : int
        Total number of writer-reader pairs generating load.
    num_pravega_instances : int
        Number of Pravega segment store instances currently active.
    num_samples : int
        Number of latency samples to draw for the current slot.

    Returns
    -------
    list[float]
        Synthetic latency values for the given configuration.
    """
    per_segment_store_writers_distribution = [
        load for load in distribute_load(int(num_writer_reader_pairs),
                                         int(num_pravega_instances)) if load > 0
    ]
    latency_values = []
    for load in per_segment_store_writers_distribution:
        for latency in np.concatenate(
            random.choices(io_e2e_latency_measurements[load], k=num_samples)
        ).tolist():
            latency_values.append(latency)
    return latency_values


def fixed_scaling_policy(num_writer_reader_pairs, num_pravega_instances, last_slots_latencies, prediction_values):
    """
    Fixed Pravega auto-scaling policy.

    Ignores workload and latency. Always returns a constant number of instances.

    Returns
    -------
    int
        Always returns 2.
    """
    return 2


def reactive_scaling_policy(num_writer_reader_pairs, num_pravega_instances, last_slots_latencies, prediction_values):
    """
    Reactive Pravega auto-scaling policy.

    Scales the number of instances based on observed latency distributions
    from recent slots. If latency exceeds SLA bounds, scale up. If latency
    is below lower bound, scale down (with optional memory to avoid thrashing).

    Parameters
    ----------
    num_writer_reader_pairs : int
        Number of writer-reader pairs.
    num_pravega_instances : int
        Current number of Pravega instances.
    last_slots_latencies : list[list[float]]
        Latency samples from recent slots.
    prediction_values : list[float]
        Prediction values (unused by this policy).

    Returns
    -------
    int
        Updated number of Pravega instances.
    """
    global latency_percentile
    global latency_threshold
    global last_scaling_latency
    global last_writers_per_instance
    global latency_tolerance_percentage
    global reactive_scaling_with_memory

    latency_upper_bound = latency_threshold + latency_threshold * latency_tolerance_percentage / 100
    latency_lower_bound = latency_threshold - latency_threshold * latency_tolerance_percentage / 100
    observed_latency_percentile = np.percentile(
        [latency for slot_latencies in last_slots_latencies for latency in slot_latencies],
        latency_percentile
    )

    current_writers_per_instance = num_writer_reader_pairs / num_pravega_instances

    if observed_latency_percentile > latency_upper_bound:
        last_scaling_latency = observed_latency_percentile
        last_writers_per_instance = current_writers_per_instance
        return num_pravega_instances + 1
    elif (observed_latency_percentile < latency_lower_bound and num_pravega_instances > 1):
        if (reactive_scaling_with_memory and last_writers_per_instance <= current_writers_per_instance):
            print("NOT Scaling down - last_writers_per_instance: ", last_writers_per_instance,
                  " current_writers_per_instance: ", current_writers_per_instance)
            return num_pravega_instances
        print("Scaling down - last_writers_per_instance: ", last_writers_per_instance,
              " current_writers_per_instance: ", current_writers_per_instance)
        last_scaling_latency = observed_latency_percentile
        last_writers_per_instance = current_writers_per_instance
        return num_pravega_instances - 1
    else:
        return num_pravega_instances


def predictive_scaling_policy(num_writer_reader_pairs, num_pravega_instances, last_slots_latencies, prediction_values):
    """
    Predictive "oracle" auto-scaling policy for Pravega.

    Uses future workload predictions (trace-based forecasts) to decide
    scaling before SLA violations occur. Iteratively evaluates how many
    instances are needed to satisfy latency bounds.

    Parameters
    ----------
    num_writer_reader_pairs : int
        Number of writer-reader pairs.
    num_pravega_instances : int
        Current number of Pravega instances.
    last_slots_latencies : list[list[float]]
        Latency samples from recent slots.
    prediction_values : list[float]
        Predicted future workload values.

    Returns
    -------
    int
        Updated number of Pravega instances needed to meet SLA.
    """
    global latency_percentile
    global latency_threshold
    global latency_tolerance_percentage
    global last_scaling_latency
    global do_next_prediction
    global prediction_window

    print(do_next_prediction)
    max_forecasted_writers_next_window = max(prediction_values)
    do_next_prediction += 1
    if do_next_prediction % prediction_window != 0:
        return num_pravega_instances
    if max_forecasted_writers_next_window == 0:
        return 1

    min_pravega_instances_meet_latency = num_pravega_instances
    forecasted_latency = io_e2e_latency_modelling(max_forecasted_writers_next_window,
                                                  min_pravega_instances_meet_latency,
                                                  100)
    forecasted_latency_percentile = np.percentile(forecasted_latency, latency_percentile)
    latency_upper_bound = latency_threshold + latency_threshold * latency_tolerance_percentage / 100
    latency_lower_bound = latency_threshold - latency_threshold * latency_tolerance_percentage / 100
    increase_instances = forecasted_latency_percentile > latency_upper_bound
    if increase_instances:
        while True:
            forecasted_latency = io_e2e_latency_modelling(max_forecasted_writers_next_window,
                                                          min_pravega_instances_meet_latency,
                                                          100)
            forecasted_latency_percentile = np.percentile(forecasted_latency, latency_percentile)
            if forecasted_latency_percentile > latency_upper_bound:
                last_scaling_latency = forecasted_latency_percentile
                min_pravega_instances_meet_latency += 1
            else:
                return min_pravega_instances_meet_latency
    else:
        while min_pravega_instances_meet_latency > 1 and forecasted_latency_percentile < latency_lower_bound:
            forecasted_latency = io_e2e_latency_modelling(max_forecasted_writers_next_window,
                                                          min_pravega_instances_meet_latency - 1,
                                                          100)
            forecasted_latency_percentile = np.percentile(forecasted_latency, latency_percentile)
            if forecasted_latency_percentile < latency_lower_bound:
                min_pravega_instances_meet_latency -= 1
        return min_pravega_instances_meet_latency


def load_trace_file(file_path):
    """
    Load a workload trace file.

    Parameters
    ----------
    file_path : str
        Path to a text file where each line contains a numeric value.

    Returns
    -------
    list[float]
        Trace values loaded from the file.
    """
    trace_values = []
    with open(file_path, 'r') as file:
        for line in file:
            try:
                trace_values.append(float(line.strip()))
            except ValueError:
                print(f"Skipping line: {line.strip()}, not a valid numerical value")
    return trace_values


def simulate(trace_path, prediction_path, pravega_scaling_policy, latency_file_name, instances_file_name):
    """
    Run an I/O latency and scaling simulation.

    Parameters
    ----------
    trace_path : str
        Path to the workload trace file.
    prediction_path : str
        Path to the prediction trace file.
    pravega_scaling_policy : callable
        Scaling policy function to use (reactive, predictive, etc.).
    latency_file_name : str
        Output CSV file for latency percentiles.
    instances_file_name : str
        Output CSV file for number of instances.

    Returns
    -------
    None
    """
    global scaling_latency_penalty_mean
    global scaling_latency_penalty_std_dev
    global trace_starting_slot
    global training_starting_slot
    global prediction_window
    global trace_to_process

    num_pravega_instances = 1
    old_pravega_instances = 1
    last_slots_latencies = []

    trace_values = load_trace_file(trace_path)
    prediction_values = load_trace_file(prediction_path)
    prediction_values = prediction_values[training_starting_slot:]
    trace_values = trace_values[trace_starting_slot:]

    latency_percentiles_file = open(latency_file_name, "w")
    num_segment_stores_file = open(instances_file_name, "w")
    latency_percentiles_file.write("25th, 50th, 75th, 90th, 95th, 99th, max\n")

    while not trace_values == []:
        num_writer_reader_pairs = trace_values.pop(0) * cameras_per_surgery
        print(len(trace_values))
        latency_samples = int(FPS * num_writer_reader_pairs * seconds_per_slot)
        if latency_samples > 0:
            new_latencies = io_e2e_latency_modelling(num_writer_reader_pairs, num_pravega_instances, latency_samples)
            scaling_penalty_latencies = add_autoscaling_latency_penalty(old_pravega_instances, num_pravega_instances,
                                                                        num_writer_reader_pairs)
            new_latencies += scaling_penalty_latencies
            last_slots_latencies.append(new_latencies)
            latency_percentiles = np.percentile(last_slots_latencies[-1], [25, 50, 75, 90, 95, 99, 100])
            latency_percentiles_file.write(
                "{}, {}, {}, {}, {}, {}, {}\n".format(latency_percentiles[0], latency_percentiles[1],
                                                      latency_percentiles[2], latency_percentiles[3],
                                                      latency_percentiles[4], latency_percentiles[5],
                                                      latency_percentiles[6]))
        else:
            last_slots_latencies.append([0])
            latency_percentiles_file.write("0, 0, 0, 0, 0, 0, 0\n")

        if len(last_slots_latencies) > prediction_window:
            last_slots_latencies.pop(0)

        old_pravega_instances = num_pravega_instances
        num_pravega_instances = pravega_scaling_policy(num_writer_reader_pairs,
                                                       num_pravega_instances,
                                                       last_slots_latencies,
                                                       prediction_values[:prediction_window])

        num_segment_stores_file.write("{}\n".format(num_pravega_instances))
        prediction_values.pop(0)

        if trace_to_process == 0:
            break
        trace_to_process -= 1

    latency_percentiles_file.close()
    num_segment_stores_file.close()


def add_autoscaling_latency_penalty(old_pravega_instances, num_pravega_instances, num_writer_reader_pairs):
    """
    Apply additional latency penalties caused by scaling events.

    Parameters
    ----------
    old_pravega_instances : int
        Number of instances before scaling.
    num_pravega_instances : int
        Number of instances after scaling.
    num_writer_reader_pairs : int
        Workload size to determine impacted writers.

    Returns
    -------
    list[float]
        List of synthetic latency penalty values.
    """
    latency_penalty = []
    if num_pravega_instances != old_pravega_instances:
        writers_impacted = round(num_writer_reader_pairs * (1.0 - min(num_pravega_instances, old_pravega_instances)
                                                            / max(num_pravega_instances, old_pravega_instances)))
        print("Writers impacted: ", writers_impacted)
        latency_penalty = np.random.normal(loc=scaling_latency_penalty_mean,
                                           scale=scaling_latency_penalty_std_dev,
                                           size=writers_impacted).tolist()
    return latency_penalty


def load_csv_files_to_dict(directory_path):
    """
    Load a set of CSV files into a dictionary keyed by file order.

    Parameters
    ----------
    directory_path : str
        Path to the directory containing CSV files.

    Returns
    -------
    dict[int, numpy.ndarray]
        Dictionary where keys are file indices (1-based) and values
        are data arrays loaded from the CSV files.
    """
    data_dict = {}
    files = sorted([f for f in os.listdir(directory_path) if f.endswith('.csv')],
                   key=lambda s: int(s.split("-")[0]))
    print(files)

    key = 1
    for file in files:
        file_path = os.path.join(directory_path, file)
        df = pd.read_csv(file_path)
        data_array = df.values
        data_dict[key] = data_array
        key += 1
    return data_dict


def calculate_percentage_above_threshold(file_path, column_name, threshold):
    """
    Calculate percentage of values above a threshold in a CSV column.

    Parameters
    ----------
    file_path : str
        Path to the CSV file.
    column_name : str
        Column name to analyze.
    threshold : float
        Threshold value to compare against.

    Returns
    -------
    float
        Percentage of values above threshold (0.0 if column is empty).
    """
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip()
    if column_name not in df.columns:
        raise ValueError(f"Column '{column_name}' not found in the CSV file.")
    column_data = df[column_name]
    above_threshold = column_data[column_data > threshold].count()
    total_values = column_data.count()
    if total_values == 0:
        return 0.0
    percentage_above_threshold = (above_threshold / total_values) * 100
    return percentage_above_threshold


def log_latency_violations(results_file_name, latency_file_name):
    """
    Log the percentage of latency violations with respect to
    SLA lower bound, threshold, and upper bound.

    Parameters
    ----------
    results_file_name : str
        Output file for latency violation percentages.
    latency_file_name : str
        Input file containing latency percentiles.
    """
    global latency_threshold
    global latency_tolerance_percentage

    percentage_above_threshold = calculate_percentage_above_threshold(latency_file_name, "95th", latency_threshold)
    latency_upper_bound = latency_threshold + latency_threshold * latency_tolerance_percentage / 100
    latency_lower_bound = latency_threshold - latency_threshold * latency_tolerance_percentage / 100
    percentage_above_threshold_lower = calculate_percentage_above_threshold(latency_file_name, "95th", latency_lower_bound)
    percentage_above_threshold_upper = calculate_percentage_above_threshold(latency_file_name, "95th", latency_upper_bound)
    latency_violation_file = open(results_file_name, "w")
    latency_violation_file.write("Over lower bound ({}), Over threshold ({}), Over upper bound ({})\n"
                                 .format(latency_lower_bound, latency_threshold, latency_upper_bound))
    latency_violation_file.write("{}, {}, {}\n".format(percentage_above_threshold_lower, percentage_above_threshold,
                                                       percentage_above_threshold_upper))
    latency_violation_file.close()


def log_instance_autoscaling_events_and_time(results_file_name_events, results_file_name_time, file_path):
    """
    Count and log the number of autoscaling events and total instance time.

    Parameters
    ----------
    results_file_name_events : str
        Output file for the number of autoscaling events.
    results_file_name_time : str
        Output file for total instance time.
    file_path : str
        Path to the CSV file containing instance counts (no header).
    """
    df = pd.read_csv(file_path, header=None)
    if 0 >= len(df.columns):
        raise ValueError(f"Column index '{0}' is out of range for the CSV file.")
    column_data = df.iloc[:, 0]
    changes = (column_data.shift(1) != column_data).sum() - 1
    autoscaling_events_file = open(results_file_name_events, "w")
    autoscaling_events_file.write("{}\n".format(changes))
    autoscaling_events_file.close()
    instance_time_file = open(results_file_name_time, "w")
    instance_time_file.write("{}\n".format(column_data.sum()))
    instance_time_file.close()


if __name__ == '__main__':
    # Default parameters for running experiments.
    FPS = 30
    seconds_per_slot = 60
    last_scaling_latency = 0
    do_next_prediction = 0
    latency_percentile = 95
    latency_threshold = 20
    latency_tolerance_percentage = 10
    cameras_per_surgery = 1
    scaling_latency_penalty_mean = 100
    scaling_latency_penalty_std_dev = 10
    trace_to_process = 10080

    # Initialize the IO latency modelling.
    # data = np.loadtxt('../resources/e2e_latency.csv')
    # io_e2e_latency_params = genextreme.fit(data)
    io_e2e_latency_measurements = load_csv_files_to_dict('../resources/pravega_io_latency_measurements/')

    # Run IO simulation for this trace.
    # simulate('../resources/nct.csv', '../resources/nct.csv', 0, 1, fixed_scaling_policy,
    #    "latency_percentiles_fixed_1.csv", "num_segment_stores_fixed_1.csv")

    ### REACTIVE SCALING POLICY
    #trace_starting_slot = 10080
    #training_starting_slot = 10080
    #prediction_window = 20
    #method_name = "reactive_vanilla"
    #reactive_scaling_with_memory = False
    #experiment_config = "_{}ms_{}p_{}min".format(latency_threshold, latency_percentile, prediction_window)
    #latency_file_name = "../results/" + method_name + experiment_config + "_latency_percentiles.csv"
    #num_instances_file_name = "../results/" + method_name + experiment_config + "_num_segment_stores.csv"
    #simulate('../resources/nct.csv', '../resources/nct.csv', reactive_scaling_policy,
    #        latency_file_name, num_instances_file_name)

    ### REACTIVE SCALING POLICY WITH MEMORY
    #trace_starting_slot = 10080
    #training_starting_slot = 10080
    #prediction_window = 5
    #method_name = "reactive_memory"
    #reactive_scaling_with_memory = True
    #experiment_config = "_{}ms_{}p_{}min".format(latency_threshold, latency_percentile, prediction_window)
    #latency_file_name = "../results/" + method_name + experiment_config + "_latency_percentiles.csv"
    #num_instances_file_name = "../results/" + method_name + experiment_config + "_num_segment_stores.csv"
    #simulate('../resources/nct.csv', '../resources/nct.csv', reactive_scaling_policy,
    #         latency_file_name, num_instances_file_name)


    ### ORACLE PREDICTIVE SCALING POLICY
    #trace_starting_slot = 10080
    #training_starting_slot = 10080
    #prediction_window = 20
    #method_name = "predictive_oracle"
    #experiment_config = "_{}ms_{}p_{}min".format(latency_threshold, latency_percentile, prediction_window)
    #latency_file_name = "../results/" + method_name + experiment_config + "_latency_percentiles.csv"
    #num_instances_file_name = "../results/" + method_name + experiment_config + "_num_segment_stores.csv"
    #simulate('../resources/nct.csv', '../resources/nct.csv',
    #         predictive_scaling_policy, latency_file_name, num_instances_file_name)

    ### LSTM PREDICTIVE SCALING POLICY
    trace_starting_slot = 10080
    training_starting_slot = 0
    prediction_window = 20
    method_name = "predictive_lstm"
    experiment_config = "_{}ms_{}p_{}min".format(latency_threshold, latency_percentile, prediction_window)
    latency_file_name = "../results/" + method_name + experiment_config + "_latency_percentiles.csv"
    num_instances_file_name = "../results/" + method_name + experiment_config + "_num_segment_stores.csv"
    simulate('../resources/nct.csv', '../resources/predictions_open_loop.csv',
             predictive_scaling_policy, latency_file_name, num_instances_file_name)


    log_latency_violations("../results/" + method_name + experiment_config + "_latency_violations.csv", latency_file_name)
    log_instance_autoscaling_events_and_time("../results/" + method_name + experiment_config + "_autoscaling_events.csv",
                                    "../results/" + method_name + experiment_config + "_instance_time.csv",
                                    num_instances_file_name)
