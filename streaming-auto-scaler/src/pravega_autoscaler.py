"""
Pravega Trace-Based Autoscaler

This module provides functionality to automatically scale the number of Pravega
segment store instances based on a trace file or external input. It uses the
Kubernetes Python client to patch the `PravegaCluster` custom resource in order
to adjust the number of segment store replicas dynamically.
"""

from kubernetes import client, config
from kubernetes.client.rest import ApiException

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
        self.api_client = client.ApiClient()
        self.custom_objects_api = client.CustomObjectsApi()

    def run(self, new_num_pods):
        """
        Apply a scaling decision to change the number of segment store pods.
        Args:
            new_num_pods (int): Desired number of segment store pods.
        """
        self.change_segment_store_replicas(new_num_pods)


    def change_segment_store_replicas(self, num_segmentstores, namespace=None):
        """
        Patch the PravegaCluster custom resource to change segment store replicas.
        Args:
            num_segmentstores (int): Target number of segment store replicas.
            namespace (str, optional): Kubernetes namespace. Defaults to instance's namespace.
        """
        if namespace is None:
            namespace = self.namespace

        try:
            patch_body = {
                "spec": {
                    "pravega": {
                        "segmentStoreReplicas": num_segmentstores
                    }
                }
            }

            response = self.custom_objects_api.patch_namespaced_custom_object(
                group="pravega.pravega.io",
                version="v1beta1",
                namespace=namespace,
                plural="pravegaclusters",
                name="pravega",
                body=patch_body,
            )

            print(f"PravegaAutoscalerGenerator - Successfully patched PravegaCluster.")
            print(f"Updated Segment Store Count: {num_segmentstores}")

        except ApiException as e:
            print(f"PravegaAutoscalerGenerator - API Exception when patching PravegaCluster:")
            print(f"Status: {e.status}")
            print(f"Reason: {e.reason}")
            print(f"Body: {e.body}")
        except Exception as e:
            print(f"PravegaAutoscalerGenerator - Unexpected error when patching PravegaCluster: {e}")






