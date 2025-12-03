# A script to delete all scopes from Pravgea as per their storage in MinIO

import subprocess
from minio import Minio

MINIO_ENDPOINT = "localhost:9000"
BUCKET_NAME = "pravega-lts"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
PRAVEGA_CLI_PATH = "/home/ubuntu/pravega-0.13.0/bin/pravega-cli"
STREAM_NAMES = ["latency", "latency-index"]

def delete_stream(scope_name, stream_name):
    try:
        result = subprocess.run([
            PRAVEGA_CLI_PATH,
            "stream", "delete",
            f"{scope_name}/{stream_name}"
        ], check=True, capture_output=True, text=True)
        print(f"[INFO] Deleted stream '{stream_name}' in scope '{scope_name}'.")
    except subprocess.CalledProcessError as e:
        if "not found" not in e.stderr.lower():
            print(f"[ERROR] Failed to delete stream '{stream_name}': {e.stderr}")
        else:
            print(f"[WARN] Stream '{stream_name}' not found.")


def delete_scope(scope_name):
    try:
        result = subprocess.run([
            PRAVEGA_CLI_PATH,
            "scope", "delete",
            scope_name
        ], check=True, capture_output=True, text=True)
        print(f"[INFO] Deleted scope '{scope_name}'.")
    except subprocess.CalledProcessError as e:
        if "not found" not in e.stderr.lower():
            print(f"[ERROR] Failed to delete scope '{scope_name}': {e.stderr}")
        else:
            print(f"[WARN] Scope '{scope_name}' not found.")


def get_scope_names_from_minio():
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False 
    )

    scope_names = set()
    objects = client.list_objects(BUCKET_NAME)

    for obj in objects:
        if obj.object_name.endswith('/'):
            folder_name = obj.object_name.rstrip('/')
            if folder_name != "_system":
                scope_names.add(folder_name)

    return list(scope_names)


def main():
    scopes = get_scope_names_from_minio()
    print(f"[INFO] Found {len(scopes)} scopes to delete: {scopes}")

    for scope in scopes:
        print(f"\n[START] Cleaning up scope: {scope}")
        for stream_name in STREAM_NAMES:
            delete_stream(scope, stream_name)
        delete_scope(scope)
        print(f"[END] Finished cleaning up scope: {scope}\n")


if __name__ == "__main__":
    main()