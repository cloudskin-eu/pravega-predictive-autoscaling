"""
Video Workload Generator for Pravega + Kubernetes.

This script automates the deployment of paired latency writer/reader pods 
to a Kubernetes cluster for benchmarking video ingestion latency with Pravega.

It supports:
- Instantiating pods from inline YAML definitions.
- Scaling the number of writer/reader pairs up or down.
- Cleaning up pods when scaling down.

"""

from kubernetes import client, config
import time
import subprocess
import os


# --------------------------------------------------------------------
# Configuration constants (Pod template, Docker image, Pravega params)
# --------------------------------------------------------------------
PODNAME = "PODNAME"
NODENAME = "NODENAME"
NODES = 3

docker_image = 'xxxx.dkr.ecr.us-east-1.amazonaws.com/gstreamer:pravega-prod-latency'  # Private ECR image
pod_yaml = "apiVersion: v1\n" + \
           "kind: Pod\n" + \
           "metadata:\n" + \
           "    name: " + PODNAME + "\n" + \
           "spec:\n" + \
           "  containers:\n" + \
           "    - name: " + PODNAME + "\n" + \
           "      image: " + docker_image + "\n" + \
           "      imagePullPolicy: Always\n" + \
           "      env:\n" + \
           "        - name: ENTRYPOINT\n" + \
           "          value: "
root_permission = "      securityContext:\n" + \
                  "        allowPrivilegeEscalation: false\n" + \
                  "        runAsUser: 0\n"
docker_run_file = "docker run --rm --network host --privileged --user root --log-driver json-file --log-opt max-size=10m " + \
                  "--log-opt max-file=2 -e ENTRYPOINT="
entrypoint_writer = "/usr/src/gstreamer-pravega/python_apps/pravega_latency_writer.py " + \
                    "--pravega-controller-uri %s --scope %s --stream %s --pravega-buffer-size %s " + \
                    "--video-height %s --video-width %s --video-fps %s --video-bitrate %s --sleep-seconds %s"
entrypoint_reader = "/usr/src/gstreamer-pravega/python_apps/pravega_latency_reader.py " + \
                    "--pravega-controller-uri %s --scope %s --stream %s --sleep-seconds %s"

# Pravega stream configuration
pravega_controller_uri = "pravega-pravega-controller:9090"
scope = "test"
stream = "latency"
pravega_buffer_size = 1024

# Video parameters
video_height = 1280
video_width = 720
video_fps = 30
video_bitrate = 5000

# Sleep times for workload pacing
writer_sleep_seconds = 0.0
reader_sleep_seconds = 5.0


def instantiate_pod(pod_name, pod_manifest):
    """
    Create and deploy a Kubernetes pod from the given YAML manifest.

    Args:
        pod_name (str): Name of the pod to create.
        pod_manifest (str): Inline YAML definition of the pod.

    Side effects:
        - Writes the manifest to a temporary YAML file.
        - Calls `kubectl create -f` to deploy the pod.
        - Deletes the temporary YAML file afterwards.
    """
    try:
        yaml_path = "./" + pod_name + ".yaml"
        writer_yaml_file = open(yaml_path, 'a')
        writer_yaml_file.write(pod_manifest)
        writer_yaml_file.close()
        # Deploy pod.
        command = ["kubectl", "create", "-f", yaml_path]
        result = subprocess.run(command, capture_output=True, check=True, text=True)
        os.remove(yaml_path)
    except subprocess.CalledProcessError as e:
        print(f"VideoWorkloadGenerator - Error invoking the script: {e}")

    print(f"VideoWorkloadGenerator - Pod {pod_name} instantiated.")


def delete_pod(api_instance, namespace, pod_name):
    """
    Delete a Kubernetes pod in the given namespace.

    Args:
        api_instance: Kubernetes CoreV1Api instance.
        namespace (str): Namespace containing the pod.
        pod_name (str): Name of the pod to delete.
    """
    api_instance.delete_namespaced_pod(name=pod_name, namespace=namespace)
    print(f"VideoWorkloadGenerator - Pod {pod_name} deleted.")


class VideoWorkloadGenerator:
    """
    Automates scaling of video workload pods in Kubernetes.

    Each scaling step deploys or removes pairs of:
    - A latency writer pod (produces video data into Pravega).
    - A latency reader pod (consumes video data for benchmarking).
    """

    def __init__(self, namespace):
        """
        Initialize the workload generator.

        Args:
            namespace (str): Kubernetes namespace where pods should run.
        """
        self.namespace = namespace

    def run(self, new_num_pods):
        """
        Scale the number of writer/reader pod pairs to `new_num_pods`.

        Args:
            new_num_pods (int): Desired number of writer/reader pairs.

        Behavior:
            - If scaling up, new writer/reader pods are created with unique IDs.
            - If scaling down, excess pods are deleted.
            - If unchanged, prints a no-op message.
        """
        new_num_pods = int(new_num_pods)  # We instantiate a pair of writer/reader on each scaling step.
        config.load_kube_config()  # Load kube config from ~/.kube/config

        v1 = client.CoreV1Api()

        current_benchmark_pods = sorted(
            [pod.metadata.name for pod in v1.list_namespaced_pod(namespace=self.namespace).items if "latency" in pod.metadata.name]
        )
        current_num_benchmark_pods = len(current_benchmark_pods)

        if new_num_pods * 2 > current_num_benchmark_pods:
            for i in range(int(current_num_benchmark_pods / 2), new_num_pods):
                experiment_id = int(time.time()) + i  # random.randint(1, 100000)
                writer_name = str(experiment_id) + "-latency-writer"
                configured_writer_entrypoint = entrypoint_writer % (
                    pravega_controller_uri,
                    scope + str(experiment_id),
                    stream,
                    pravega_buffer_size,
                    video_height,
                    video_width,
                    video_fps,
                    video_bitrate,
                    writer_sleep_seconds,
                )
                writer_manifest = pod_yaml.replace(PODNAME, writer_name) + "\"" + configured_writer_entrypoint + "\"\n"
                instantiate_pod(writer_name, writer_manifest)

                reader_name = str(experiment_id) + "-latency-reader"
                configured_reader_entrypoint = entrypoint_reader % (
                    pravega_controller_uri,
                    scope + str(experiment_id),
                    stream,
                    reader_sleep_seconds,
                )
                reader_manifest = (
                    pod_yaml.replace(PODNAME, reader_name) + "\"" + configured_reader_entrypoint + "\"\n" + root_permission
                )
                instantiate_pod(reader_name, reader_manifest)
        elif new_num_pods * 2 < current_num_benchmark_pods:
            for i in range(new_num_pods * 2, current_num_benchmark_pods):
                pod_name = current_benchmark_pods[i]
                delete_pod(v1, self.namespace, pod_name)
        else:
            print("VideoWorkloadGenerator - No change in the number of pods.")
