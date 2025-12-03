# Pravega Trace-Based Autoscaler

A comprehensive simulation and autoscaling system for Pravega streaming platform that combines trace-driven workload generation, latency modeling, and intelligent scaling policies to optimize performance in video ingestion scenarios.

## Overview

This project provides a complete framework for:
- **Trace-based simulation** of I/O latency and autoscaling behavior
- **Real-time autoscaling** of Pravega segment store instances
- **Video workload generation** for performance benchmarking
- **Predictive scaling** using LSTM models for proactive resource management

The system is designed for surgical video streaming applications but can be adapted for other high-throughput streaming scenarios.

## Architecture

```
├── pravega_autoscaler.py      # Core Kubernetes autoscaler
├── simulator.py               # Latency simulation and scaling policies
├── trace_player.py            # Trace file replay orchestration
├── workload_executors.py      # Kubernetes workload generator
└── workload_prediction_model_lstm.py  # LSTM prediction model
```

## Features

### Scaling Policies
- **Fixed Scaling**: Maintains constant number of instances
- **Reactive Scaling**: Responds to SLA violations with optional memory to prevent thrashing
- **Predictive Scaling**: Uses LSTM models or oracle predictions for proactive scaling

### Latency Modeling
- Empirical latency distributions based on writers-per-instance ratios
- Configurable SLA thresholds and tolerance percentages
- Scaling penalty simulation for realistic transition costs

### Workload Generation
- Paired writer/reader pod deployment
- Video ingestion simulation with configurable parameters
- Automatic Kubernetes resource management

## Installation

### Prerequisites
- Python 3.7+
- Kubernetes cluster with kubectl configured
- Pravega cluster deployed in Kubernetes
- Required Python packages:

```bash
pip install kubernetes numpy pandas matplotlib tensorflow scikit-learn
```

### Setup
1. Clone the repository
2. Configure your Kubernetes context to point to your cluster
3. Update the Docker image reference in `workload_executors.py`
4. Prepare your latency measurement CSVs in `../resources/pravega_io_latency_measurements/`

## Usage

### Basic Autoscaling
```python
from pravega_autoscaler import PravegaTraceBasedAutoscaler

# Initialize autoscaler for 'default' namespace
autoscaler = PravegaTraceBasedAutoscaler('default')

# Scale to 5 segment store instances
autoscaler.run(5)
```

### Running Simulations
```python
from simulator import simulate, reactive_scaling_policy

# Run reactive scaling simulation
simulate(
    trace_path='../resources/workload_trace.csv',
    prediction_path='../resources/predictions.csv',
    pravega_scaling_policy=reactive_scaling_policy,
    latency_file_name='results/latency_percentiles.csv',
    instances_file_name='results/num_instances.csv'
)
```

### Trace-based Workload Replay
```python
from trace_player import process_trace_file
from workload_executors import VideoWorkloadGenerator

# Replay trace file to scale video workload
process_trace_file(
    file_path='../resources/workload_trace.csv',
    processing_callback=VideoWorkloadGenerator('default').run,
    time_unit='minutes',
    replay_speed=20,
    do_sleep=True
)
```

### Training LSTM Prediction Model
```python
from workload_prediction_model_lstm import build_model_from_trace

# Train LSTM model on historical data
build_model_from_trace()
```

## Configuration

### Simulation Parameters
Edit the global variables in `simulator.py`:

```python
FPS = 30                              # Frames per second per camera
seconds_per_slot = 60                 # Simulation slot duration
latency_threshold = 20                # Target latency (ms)
latency_tolerance_percentage = 10     # SLA tolerance
cameras_per_surgery = 1               # Workload scaling factor
scaling_latency_penalty_mean = 100    # Scaling transition penalty
```

### Video Workload Parameters
Configure in `workload_executors.py`:

```python
video_height = 1280
video_width = 720
video_fps = 30
video_bitrate = 5000
pravega_controller_uri = "pravega-pravega-controller:9090"
```

## File Structure

### Input Files
- `../resources/nct.csv` - Workload trace data
- `../resources/predictions_open_loop.csv` - LSTM predictions
- `../resources/pravega_io_latency_measurements/` - Empirical latency CSVs

### Output Files
- `../results/*_latency_percentiles.csv` - Latency distribution results
- `../results/*_num_segment_stores.csv` - Instance count over time
- `../results/*_latency_violations.csv` - SLA violation analysis
- `../results/*_autoscaling_events.csv` - Scaling event count

## Scaling Policies

### Reactive Policy
Monitors latency percentiles and scales when SLA bounds are exceeded:
- Scale up when latency > threshold + tolerance
- Scale down when latency < threshold - tolerance
- Optional memory to prevent oscillation

### Predictive Policy
Uses future workload predictions to scale proactively:
- Oracle mode: Uses perfect future knowledge
- LSTM mode: Uses trained prediction models
- Evaluates minimum instances needed for forecasted load

## Monitoring and Analysis

The system provides comprehensive metrics:
- **Latency percentiles** (25th, 50th, 75th, 90th, 95th, 99th)
- **SLA violation rates** for different thresholds
- **Autoscaling event frequency**
- **Total instance-time consumption**

## Example Experiments

### Reactive Scaling with Memory
```python
trace_starting_slot = 10080
prediction_window = 20
reactive_scaling_with_memory = True
method_name = "reactive_memory"
experiment_config = f"_{latency_threshold}ms_{latency_percentile}p_{prediction_window}min"

simulate('../resources/nct.csv', '../resources/nct.csv', 
         reactive_scaling_policy,
         f"../results/{method_name}{experiment_config}_latency_percentiles.csv",
         f"../results/{method_name}{experiment_config}_num_segment_stores.csv")
```

### LSTM Predictive Scaling
```python
method_name = "predictive_lstm"
simulate('../resources/nct.csv', '../resources/predictions_open_loop.csv',
         predictive_scaling_policy,
         f"../results/{method_name}{experiment_config}_latency_percentiles.csv",
         f"../results/{method_name}{experiment_config}_num_segment_stores.csv")
```

## Cluster Implementation
To practically execute and run the simulation results in a Kubernetes cluster, said cluster should ideally include the following prerequisites:
### Pravega
The cluster should have a **full** Pravega deployment running, with at least one **Zookeeper** and one **Bookkeeper** pods. Provided the usage of Helm to deploy, make sure to modify and use [this repo's yaml file](streaming-auto-scaler/resources/pravega_chart_values.yaml) when installing Pravega:

```bash
helm install zookeeper-operator pravega/zookeeper-operator
helm install zookeeper pravega/zookeeper
helm install bookkeeper-operator pravega/bookkeeper-operator
helm install bookkeeper pravega/bookkeeper
helm install pravega-operator pravega/pravega-operator
helm install pravega pravega/pravega -f <your modified yaml file>
```

### Long-term Storage
A long-term storage connected to Pravega. Preferably **MinIO**.

### Metrics
This project uses **InfluxDB** and **Grafana** for metrics display. Basic InfluxDB deployment and service are sufficient. For Grafana, there is [a provided dashboard](grafana-dashboard.json) in this repository that can be directly imported. When imported, make sure to add the created InfluxDB service as a data source endpoint.

#### Extra Metrics
The Grafana dashboard also leverages metrics exported by the [kube-prometheus](https://github.com/prometheus-operator/kube-prometheus) stack to display pod counts and statistics. If needed, follow the official guide to install it on the cluster and add the respective data source endpoint.

### Pods
After fully installing the mentioned resources, a typical deployment should look like this:
```bash
~$ kubectl get pods
NAME                                                     READY   STATUS 
alertmanager-prometheus-kube-prometheus-alertmanager-0   2/2     Running
bookkeeper-bookie-0                                      1/1     Running 
bookkeeper-bookie-1                                      1/1     Running
bookkeeper-bookie-2                                      1/1     Running
bookkeeper-operator-86b59c8f89-454bh                     1/1     Running
grafana-8459977b7f-qhghw                                 1/1     Running 
image-benchmark                                          1/1     Running
influxdb                                                 1/1     Running
minio-deployment-56864bd77-hrjjl                         1/1     Running
pravega-operator-6c7c9b767d-xvbv8                        1/1     Running 
pravega-pravega-controller-6857b8685c-gkstf              1/1     Running 
pravega-pravega-segment-store-0                          1/1     Running
prometheus-grafana-674cf8cb44-d4qm2                      3/3     Running
prometheus-kube-prometheus-operator-57d68989cc-ml77v     1/1     Running
prometheus-kube-state-metrics-7c5fb9d798-bhx2t           1/1     Running
prometheus-prometheus-kube-prometheus-prometheus-0       2/2     Running
prometheus-prometheus-node-exporter-69xph                1/1     Running
prometheus-prometheus-node-exporter-7b899                1/1     Running
prometheus-prometheus-node-exporter-fh9mm                1/1     Running
prometheus-prometheus-node-exporter-jf5rv                1/1     Running
prometheus-prometheus-node-exporter-nc8c4                1/1     Running
prometheus-prometheus-node-exporter-vvp2n                1/1     Running
zookeeper-0                                              1/1     Running
zookeeper-1                                              1/1     Running
zookeeper-2                                              1/1     Running
zookeeper-operator-7dd865fcdf-hv74t                      1/1     Running
```
### Run Experiment
Before execution, make sure to set up a virtual environment, and forward these ports as they are needed for resource management by the main script:
- Pravega controller
    ```bash
  kubectl port-forward svc/pravega-pravega-controller 9090:9090
    ```
- The LTS's API (MinIO in this case)
    ```bash
   kubectl port-forward svc/minio-svc 9000:9000
    ```
To run the trace playing, simply run the [main trace player script](streaming-auto-scaler/src/trace_player.py) (Preferably in its own virtual environment):
```bash
python3 trace_player.py
```
After that, the logs should indicate that the trace player is creating pods via the respective threads. Example logs:
```bash
(autoscaling) $ python3 trace_player.py
TracePlayer - Starting Pravega Autoscaler thread...
TracePlayer - Waiting 10 seconds before starting workload generator...
TracePlayer - Parsed trace value at index 0: 0.0. Now processing...
PravegaAutoscalerGenerator - Successfully patched PravegaCluster. Updated Segment Store Count: 0.0
TracePlayer - Waiting/Sleep interval for 12.00 seconds.
TracePlayer - Starting Workload Generator thread...
TracePlayer - Parsed trace value at index 0: 0.0. Now processing...
WorkloadExecutor - No change in number of workload pods.
...
```
The execution speed of the player can be modified by simply altering the `replay_speed` variable. By default, it is set to 15 (1 week of traces in 12 hours).

There are four variables holding paths for the simulation's Pravega segment store counts: 
```python
LSTM_TRACE = "streaming-auto-scaler/results/predictive_lstm_20ms_95p_20min_num_segment_stores.csv" 
REACTIVE_TRACE = "streaming-auto-scaler/results/reactive_vanilla_20ms_95p_20min_num_segment_stores.csv"
REACTIVE_MEM_TRACE = "streaming-auto-scaler/results/reactive_memory_20ms_95p_20min_num_segment_stores.csv"
ORACLE_TRACE = "streaming-auto-scaler/results/predictive_oracle_20ms_95p_20min_num_segment_stores.csv"
```
To use any one of them, simply replace the variable in the `pravega_autoscaler` thread with the desired trace.

### Results
Example results with CSVs and plots can be in the [resources](streaming-auto-scaler/resources) folder:
- `/latencies` contains p90 segment write latencies for reactive and LSTM trace runs, alongside a CDF plot 
- `/workload` contains workload and segment store pod counts for reactive and LSTM trace runs, alongside a pod count plot

## Acknowledgements

<img width="80px" src="https://cloudskin.eu/assets/img/europe.jpg">

CLOUDSKIN has received funding from the European Union’s Horizon research and innovation programme under grant agreement No 101092646.

https://cloudskin.eu/

