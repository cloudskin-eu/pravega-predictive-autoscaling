"""
Pravega Trace-Based Autoscaler

This module provides functionality to automatically scale the number of Pravega
segment store instances based on a trace file or external input. It uses the
Kubernetes Python client to patch the `PravegaCluster` custom resource in order
to adjust the number of segment store replicas dynamically.
"""

from kubernetes import config
import subprocess

# Load Kubernetes configuration from default location (~/.kube/config by default).
config.load_kube_config()


class PravegaTraceBasedAutoscaler:
    """
    Scale Pravega segment store instances up or down based on trace-driven input.

    This class encapsulates autoscaling logic. Each call to :meth:`run` adjusts
    the number of Pravega segment store pods according to the given input.
    """

    def __init__(self, namespace):
        """
        Initialize the autoscaler.

        Args:
            namespace (str): Kubernetes namespace where the Pravega cluster resides.
        """
        self.namespace = namespace

    def run(self, new_num_pods):
        """
        Apply a scaling decision to change the number of segment store pods.

        Args:
            new_num_pods (int): Desired number of segment store pods.
        """
        change_segment_store_replicas(new_num_pods)


def change_segment_store_replicas(num_segmentstores, namespace='default'):
    """
    Patch the PravegaCluster custom resource to change segment store replicas.

    Args:
        num_segmentstores (int): Target number of segment store replicas.
        namespace (str, optional): Kubernetes namespace. Defaults to 'default'.

    Side Effects:
        Executes a `kubectl patch` command to update the Pravega cluster resource.

    Logs:
        Prints a success message if the patch is applied, or an error otherwise.
    """
    command = [
        'kubectl', 'patch', 'pravegacluster', 'pravega',
        '--type', 'json',
        '-p', '[{"op":"replace","path":"/spec/pravega/segmentStoreReplicas","value":' + str(num_segmentstores) + ' }]',
        '-n', namespace
    ]
    try:
        res = subprocess.run(command, check=True)
        print(f"PravegaAutoscalerGenerator - Successfully patched {res}")
    except subprocess.CalledProcessError as e:
        print(f"PravegaAutoscalerGenerator - Error patching {res}': {e}")





