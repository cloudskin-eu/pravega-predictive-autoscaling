"""
Video Workload Generator for Pravega + Kubernetes.
This script automates the deployment of paired latency writer/reader pods 
to a Kubernetes cluster for benchmarking video ingestion latency with Pravega.
Improvements:
- Tracks active experiments explicitly instead of scanning all pods.
- More efficient pod creation/deletion.
- Cleanup upon startup.
"""

from kubernetes import client, config, utils
import time
import os
import tempfile
import subprocess
import yaml

# --------------------------------------------------------------------
# Configuration constants
# --------------------------------------------------------------------

# To clean up storage for longer experiment sessions, a pravega-cli path is advised to be provided 
# Also, make sure to port forward the controller in order for the CLI to see the K8s service
# kubectl port-forward svc/pravega-pravega-controller 9090:9090
CLI_PATH = "/home/ubuntu/pravega-0.13.0/bin/pravega-cli"

docker_image = '018573873269.dkr.ecr.us-east-1.amazonaws.com/gstreamer:pravega-prod-latency'

pod_template = """
apiVersion: v1
kind: Pod
metadata:
  name: {pod_name}
spec:
  imagePullSecrets:
    - name: aws-registry
  containers:
    - name: {container_name}
      image: {image}
      imagePullPolicy: IfNotPresent
      env:
        - name: ENTRYPOINT
          value: "{entrypoint}"
{security_context}
"""

entrypoint_writer = "/usr/src/gstreamer-pravega/python_apps/pravega_latency_writer.py " + \
                    "--pravega-controller-uri %s --scope %s --stream %s --pravega-buffer-size %s " + \
                    "--video-height %s --video-width %s --video-fps %s --video-bitrate %s --sleep-seconds %s"
entrypoint_reader = "/usr/src/gstreamer-pravega/python_apps/pravega_latency_reader.py " + \
                    "--pravega-controller-uri %s --scope %s --stream %s --sleep-seconds %s"

# Pravega stream configuration
pravega_controller_uri = "pravega-pravega-controller:9090"
scope_prefix = "test"
stream = "latency"
pravega_buffer_size = 1024

# Video parameters
video_height = 1280
video_width = 720
video_fps = 30
video_bitrate = 5000
writer_sleep_seconds = 0.0
reader_sleep_seconds = 5.0


def instantiate_pod_from_dict(k8s_client, pod_spec):
    fd, path = tempfile.mkstemp(suffix='.yaml')
    try:
        with os.fdopen(fd, 'w') as tmp:
            yaml.dump(pod_spec, tmp)
        utils.create_from_yaml(k8s_client, path)
    finally:
        os.remove(path)

def delete_pod(api_instance, namespace, pod_name, scope=None):
    # Delete the Kubernetes pod
    api_instance.delete_namespaced_pod(name=pod_name, namespace=namespace)
    print(f"Deleted pod: {pod_name}")

    try:
        if scope:
            # Delete the latency stream
            try:
                subprocess.run([
                    CLI_PATH, 
                    "stream", "delete",
                    scope + "/latency", 
                    scope + "/latency-index"
                ], check=True, capture_output=True, text=True)
                print(f"Deleted stream: {scope}")
            except subprocess.CalledProcessError as e:
                if "not found" not in e.stderr.lower():
                    print(f"Warning: Failed to delete streams of {scope}: {e.stderr}")
            
            # Delete the scope
            try:
                subprocess.run([
                    CLI_PATH, 
                    "scope", "delete", scope
                ], check=True, capture_output=True, text=True)
                print(f"Deleted scope: {scope}")
            except subprocess.CalledProcessError as e:
                if "not found" not in e.stderr.lower():
                    print(f"Warning: Failed to delete scope {scope}: {e.stderr}")
        
        
    except client.exceptions.ApiException as e:
        if e.status != 404:
            print(f"Failed to delete pod {pod_name}: {e}")
    except Exception as e:
        print(f"Unexpected error deleting pod {pod_name}: {e}")


class VideoWorkloadGenerator:
    def __init__(self, namespace):
        self.namespace = namespace
        config.load_kube_config()
        self.v1 = client.CoreV1Api()
        self.k8s_client = client.ApiClient()
        # Dictionary for current workload pods
        self.active_workloads = {}
        # On init, clean up leftover latency pods from previous runs
        self._cleanup_old_pods()
    
    def _cleanup_old_pods(self):
        pods = self.v1.list_namespaced_pod(namespace=self.namespace).items
        for pod in pods:
            if "latency" in pod.metadata.name:
                delete_pod(self.v1, self.namespace, pod.metadata.name)
    
    def run(self, new_num_pods):
        new_num_pods = int(new_num_pods)
        current_count = len(self.active_workloads)
        if new_num_pods > current_count:
            # Scale up
            for i in range(current_count, new_num_pods):
                exp_id = str(int(time.time() * 1000)) + f"-{i}"
                scope = f"{scope_prefix}{exp_id}"
                writer_name = f"{exp_id}-latency-writer"
                configured_writer_entrypoint = entrypoint_writer % (
                    pravega_controller_uri,
                    scope,
                    stream,
                    pravega_buffer_size,
                    video_height,
                    video_width,
                    video_fps,
                    video_bitrate,
                    writer_sleep_seconds,
                )
                writer_pod_spec = yaml.safe_load(pod_template.format(
                    pod_name=writer_name,
                    container_name=writer_name,
                    image=docker_image,
                    entrypoint=configured_writer_entrypoint,
                    security_context=""
                ))
                reader_name = f"{exp_id}-latency-reader"
                configured_reader_entrypoint = entrypoint_reader % (
                    pravega_controller_uri,
                    scope,
                    stream,
                    reader_sleep_seconds,
                )
                reader_pod_spec = yaml.safe_load(pod_template.format(
                    pod_name=reader_name,
                    container_name=reader_name,
                    image=docker_image,
                    entrypoint=configured_reader_entrypoint,
                    security_context="      securityContext:\n        allowPrivilegeEscalation: false\n        runAsUser: 0"
                ))
                instantiate_pod_from_dict(self.k8s_client, writer_pod_spec)
                instantiate_pod_from_dict(self.k8s_client, reader_pod_spec)
                self.active_workloads[exp_id] = {
                    "writer": writer_name,
                    "reader": reader_name,
                    "scope": scope  # Store scope for cleanup
                }
                print(f'WorkloadExecutor - Created workload pods - ID: {exp_id}')
        elif new_num_pods < current_count:
            # Scale down
            ids_to_remove = list(self.active_workloads.keys())[new_num_pods:]
            for exp_id in ids_to_remove:
                info = self.active_workloads.pop(exp_id)
                # Pass scope to delete_pod for cleanup
                delete_pod(self.v1, self.namespace, info["writer"], info.get("scope"))
                delete_pod(self.v1, self.namespace, info["reader"], info.get("scope"))
                print(f'WorkloadExecutor - Deleted workload pods - ID: {exp_id}')
        else:
            print("WorkloadExecutor - No change in number of workload pods.")