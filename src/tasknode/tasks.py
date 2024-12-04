import json
import os
import subprocess
import typer
import keyring
import requests
from rich import print
from rich.table import Table
from datetime import datetime
from zoneinfo import ZoneInfo

from tasknode.auth import get_valid_token
from tasknode.constants import API_URL


def submit(
    script: str = typer.Argument(
        ...,
        help="The Python script to run (relative to the current directory, for example 'script.py' or 'path/to/script.py')",
    ),
):
    """
    Submit a Python script to be run in the cloud.
    """
    # Get authentication token
    print("Getting authentication token...", end="", flush=True)
    try:
        access_token = get_valid_token()
        print(" done")
    except keyring.errors.KeyringError as e:
        print(" error")
        typer.echo(f"Authentication error: {str(e)}", err=True)
        raise typer.Exit(1)

    # Check if the script exists
    if not os.path.exists(script):
        typer.echo(f"Error: Script '{script}' not found", err=True)
        raise typer.Exit(1)

    # delete the tasknode_deploy folder if it already exists
    result = subprocess.run(
        ["rm", "-rf", "tasknode_deploy"], capture_output=True, text=True
    )
    if result.returncode != 0:
        typer.echo(f"Error removing existing deploy folder: {result.stderr}", err=True)
        raise typer.Exit(1)

    # create a new folder called tasknode_deploy
    print("Creating deploy folder...", end="", flush=True)
    result = subprocess.run(
        ["mkdir", "tasknode_deploy"], capture_output=True, text=True
    )
    if result.returncode != 0:
        typer.echo(f"Error creating deploy folder: {result.stderr}", err=True)
        raise typer.Exit(1)

    # remove the tasknode_deploy folder if it already exists
    result = subprocess.run(
        ["rm", "-rf", "tasknode_deploy"], capture_output=True, text=True
    )
    if result.returncode != 0:
        typer.echo(f"Error removing existing deploy folder: {result.stderr}", err=True)
        raise typer.Exit(1)

    # Copy everything in the current directory into tasknode_deploy folder, excluding specific directories
    result = subprocess.run(
        [
            "rsync",
            "-av",
            "--exclude=.git",
            "--exclude=node_modules",
            "--exclude=tasknode_deploy",
            "--exclude=__pycache__",
            "--exclude=*.pyc",
            "--exclude=*.pyo",
            "--exclude=*.pyd",
            "--exclude=.env",
            "--exclude=venv",
            "--exclude=.venv",
            "--exclude=.idea",
            "--exclude=.vscode",
            "--exclude=*.egg-info",
            "--exclude=dist",
            "--exclude=build",
            "--exclude=tasknode_deploy.zip",
            "./",
            "tasknode_deploy/",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        typer.echo(f"Error copying files: {result.stderr}", err=True)
        raise typer.Exit(1)

    # get the results of running pip freeze and filter out tasknode packages
    result = subprocess.run(["pip", "freeze"], capture_output=True, text=True)
    requirements = [
        line for line in result.stdout.splitlines() if not "tasknode" in line.lower()
    ]

    # write the filtered results to a file called requirements.txt
    with open("tasknode_deploy/requirements-tasknode.txt", "w") as f:
        f.write("\n".join(requirements))
    print(" done")

    print("Getting system info...", end="", flush=True)
    # find out which version of python is being used
    python_version = subprocess.run(
        ["python", "--version"], capture_output=True, text=True
    )

    # Determine the OS type (Windows/Mac/Linux)
    if os.name == "nt":
        os_type = "Windows"
    else:
        os_info = subprocess.run(["uname"], capture_output=True, text=True)
        os_type = "Mac" if "Darwin" in os_info.stdout else "Linux"

    run_info = {
        "python_version": python_version.stdout.strip(),
        "os_info": os_type,
        "script": script,
    }

    # write the run_info to a file called run_info.json
    with open("tasknode_deploy/run_info.json", "w") as f:
        json.dump(run_info, f)
    print(" done")

    # get the size of the tasknode_deploy folder
    unzipped_size_kb = subprocess.run(
        ["du", "-sk", "tasknode_deploy/"], capture_output=True, text=True
    )
    unzipped_mb = float(unzipped_size_kb.stdout.split()[0]) / 1024

    # zip the tasknode_deploy folder
    result = subprocess.run(
        ["zip", "-r", "tasknode_deploy.zip", "tasknode_deploy/"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        typer.echo(f"Error creating zip file: {result.stderr}", err=True)
        raise typer.Exit(1)

    # get the size of the zipped tasknode_deploy folder
    zipped_size_kb = subprocess.run(
        ["du", "-sk", "tasknode_deploy.zip"], capture_output=True, text=True
    )
    zipped_mb = float(zipped_size_kb.stdout.split()[0]) / 1024
    print("")
    print(f"Deployment size unzipped: {unzipped_mb:.2f} MB")
    print(f"Deployment size zipped: {zipped_mb:.2f} MB\n")

    # Check if the folder size is greater than 300MB
    if unzipped_mb > 300:
        typer.echo("Error: TaskNode only supports deployments up to 300MB.", err=True)
        raise typer.Exit(1)

    try:
        print("Uploading code to S3...", end="", flush=True)
        response = requests.get(
            f"{API_URL}/api/v1/jobs/get_zip_upload_url",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        upload_data = response.json()

        # Upload the zip file to S3 using the signed URL
        with open("tasknode_deploy.zip", "rb") as f:
            upload_response = requests.put(
                upload_data["signedUrl"],
                data=f,
                headers={"Content-Type": "application/zip"},
            )
            upload_response.raise_for_status()

        print(" done")
        print("\n[bold green]Successfully[/bold green] submitted task! 🚀")

    except requests.exceptions.RequestException as e:
        typer.echo(f"Upload failed: {str(e)}", err=True)
        raise typer.Exit(1)
    finally:
        # Clean up temporary files
        cleanup_result = subprocess.run(
            ["rm", "-rf", "tasknode_deploy", "tasknode_deploy.zip"],
            capture_output=True,
            text=True,
        )
        if cleanup_result.returncode != 0:
            typer.echo(
                f"Warning: Error during cleanup: {cleanup_result.stderr}", err=True
            )


def list_jobs():
    """
    List your TaskNode jobs and their statuses.
    """
    # Get authentication token
    print("Getting authentication token...", end="", flush=True)
    try:
        access_token = get_valid_token()
        print(" done")
    except keyring.errors.KeyringError as e:
        print(" error")
        typer.echo(f"Authentication error: {str(e)}", err=True)
        raise typer.Exit(1)

    offset = 0
    limit = 10
    while True:
        try:
            # Fetch jobs from the API with pagination
            response = requests.get(
                f"{API_URL}/api/v1/jobs/list",
                params={"limit": limit, "offset": offset},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            jobs_data = response.json()

            # Create and configure the table
            num_jobs = len(jobs_data["jobs"])
            total_job_count = jobs_data["total_count"]
            end_index = offset + num_jobs
            
            # Only show count details if there are more jobs than currently displayed
            title = "Your TaskNode jobs"
            if total_job_count > limit:
                title += f" ({offset + 1} - {end_index} of {total_job_count})"
            
            table = Table(title=title)
            table.add_column("Job ID", style="cyan")
            table.add_column("Status", style="magenta")
            table.add_column("Created At", style="green")
            table.add_column("Updated At", style="yellow")

            # Add rows to the table
            for job in jobs_data["jobs"]:
                # Convert UTC times to local timezone
                created_dt = datetime.fromisoformat(job["created_at"]).replace(
                    tzinfo=ZoneInfo("UTC")
                )
                updated_dt = datetime.fromisoformat(job["updated_at"]).replace(
                    tzinfo=ZoneInfo("UTC")
                )

                created_at = created_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S%z")
                updated_at = updated_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S%z")

                table.add_row(str(job["id"]), job["status"], created_at, updated_at)

            # Print the table
            print("")
            print(table)

            # If there are more jobs available
            if end_index < total_job_count:
                should_continue = typer.confirm(
                    f"\nShowing {end_index} of {total_job_count} jobs. Would you like to see the next page?"
                )
                if should_continue:
                    offset += limit
                    continue

            break

        except requests.exceptions.RequestException as e:
            typer.echo(f"Failed to fetch jobs: {str(e)}", err=True)
            raise typer.Exit(1)
