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

## License

This project is licensed under the Apache 2.0 License.

