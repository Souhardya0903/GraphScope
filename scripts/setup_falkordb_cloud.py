"""Automate FalkorDB Cloud instance creation using the official API quickstart.

Reference: https://docs.falkordb.com/cloud/quickstart
"""

import argparse
import getpass
import json
import os
import sys
import time
from pathlib import Path
import httpx


SIGNIN_URL = "https://app.falkordb.cloud/api/signin"
CREATE_INSTANCE_URL = (
    "https://api.omnistrate.cloud/2022-09-01-00/resource-instance/"
    "sp-JvkxkPhinN/falkordb/v1/prod/falkordb-free-customer-hosted/"
    "falkordb-free-falkordb-customer-hosted-model-omnistrate-multi-tenancy/free"
)


def signin(email: str, password: str) -> str:
    """Sign in to FalkorDB Cloud and return the omnistrate_token cookie value."""
    print(f"Signing in as {email}...")
    with httpx.Client(timeout=15.0) as client:
        response = client.post(
            SIGNIN_URL,
            json={"email": email, "password": password},
            headers={"Content-Type": "application/json"},
        )
        if response.status_code != 200:
            raise RuntimeError(f"Sign in failed ({response.status_code}): {response.text}")

        token = response.cookies.get("omnistrate_token")
        if not token:
            for header_val in response.headers.get_list("set-cookie"):
                if "omnistrate_token=" in header_val:
                    token = header_val.split("omnistrate_token=")[1].split(";")[0]
                    break
        if not token:
            raise RuntimeError(f"Could not extract omnistrate_token from cookies: {response.cookies}")
        print("Sign-in successful. Session token obtained.")
        return token


def create_instance(
    token: str,
    db_password: str,
    name: str = "graphscope-db",
    cloud_provider: str = "aws",
    region: str = "us-east-1",
) -> str:
    """Send create request for a Free FalkorDB instance and return instance ID."""
    print(f"Requesting creation of free instance '{name}' in {cloud_provider}/{region}...")
    headers = {
        "Cookie": f"omnistrate_token={token}",
        "Content-Type": "application/json",
    }
    payload = {
        "cloud_provider": cloud_provider,
        "region": region,
        "requestParams": {
            "name": name,
            "falkordbUser": "falkordb",
            "falkordbPassword": db_password,
        },
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(CREATE_INSTANCE_URL, headers=headers, json=payload)
        if response.status_code not in (200, 201, 202):
            raise RuntimeError(f"Create instance failed ({response.status_code}): {response.text}")
        data = response.json()
        instance_id = data.get("id")
        if not instance_id:
            raise RuntimeError(f"No instance id returned in response: {data}")
        print(f"Instance creation initiated. Instance ID: {instance_id}")
        return instance_id


def wait_for_instance(token: str, instance_id: str, max_wait_seconds: int = 300) -> dict:
    """Poll describe endpoint until instance status is RUNNING."""
    url = f"{CREATE_INSTANCE_URL}/{instance_id}"
    headers = {"Cookie": f"omnistrate_token={token}"}
    print("Waiting for instance to be provisioned (status: RUNNING)...")
    start_time = time.time()
    with httpx.Client(timeout=15.0) as client:
        while time.time() - start_time < max_wait_seconds:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                print(f"Current status: {status} ({int(time.time() - start_time)}s elapsed)")
                if status == "RUNNING":
                    print("Instance is ready!")
                    return data
                elif status in ("FAILED", "ERROR"):
                    raise RuntimeError(f"Instance provisioning failed: {data}")
            else:
                print(f"Warning: describe returned {response.status_code}: {response.text}")
            time.sleep(10)
    raise TimeoutError(f"Instance was not ready within {max_wait_seconds} seconds.")


def update_env_file(host: str, port: int, password: str) -> None:
    """Update .env file with new connection settings."""
    env_path = Path(".env")
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    new_vars = {
        "FALKORDB_HOST": host,
        "FALKORDB_PORT": str(port),
        "FALKORDB_USERNAME": "falkordb",
        "FALKORDB_PASSWORD": password,
    }

    updated_keys = set()
    output_lines = []
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k = line.split("=", 1)[0].strip()
            if k in new_vars:
                output_lines.append(f"{k}={new_vars[k]}")
                updated_keys.add(k)
                continue
        output_lines.append(line)

    for k, v in new_vars.items():
        if k not in updated_keys:
            output_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    print(f"Updated .env with FALKORDB_HOST={host}, FALKORDB_PORT={port}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Automate FalkorDB Cloud instance setup.")
    parser.add_argument("--email", default=os.environ.get("FALKORDB_EMAIL"))
    parser.add_argument("--password", default=os.environ.get("FALKORDB_ACCOUNT_PASSWORD"))
    parser.add_argument("--db-password", default=os.environ.get("FALKORDB_PASSWORD"))
    parser.add_argument("--name", default="graphscope-db")
    args = parser.parse_args()

    email = args.email or input("Enter FalkorDB Cloud account email: ").strip()
    password = args.password or getpass.getpass("Enter FalkorDB Cloud account password: ").strip()
    db_password = args.db_password or getpass.getpass("Enter desired FalkorDB DB password: ").strip()

    token = signin(email, password)
    instance_id = create_instance(token, db_password, name=args.name)
    details = wait_for_instance(token, instance_id)

    result_params = details.get("result_params", {})
    endpoint = (
        result_params.get("endpoint")
        or result_params.get("host")
        or details.get("endpoint")
    )
    port = int(result_params.get("port", 6379))

    if endpoint and ":" in str(endpoint):
        parts = endpoint.split(":")
        endpoint = parts[0]
        port = int(parts[1])

    print(f"Provisioned FalkorDB instance: {endpoint}:{port}")
    update_env_file(endpoint, port, db_password)
    print("Setup complete! You can now run: python scripts/check_falkordb.py")


if __name__ == "__main__":
    main()
