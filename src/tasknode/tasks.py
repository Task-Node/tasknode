from datetime import datetime
import json
import os
import requests
import pkg_resources
import platform
from rich import print
from rich.table import Table
import shutil
import sys
import typer
import zipfile
from zoneinfo import ZoneInfo

from tasknode.auth import get_valid_token
from tasknode.constants import API_URL


def submit(
    script: str = typer.Argument(
        ...,
        help="The Python script or Jupyter notebook to run (relative to the current directory, for example 'script.py', 'path/to/script.py', or 'notebook.ipynb')",
    ),
):
    """
    Submit a Python script or Jupyter notebook to be run in the cloud.
    """
    # Get authentication token
    print("Getting authentication token... ", end="", flush=True)
    try:
        access_token = get_valid_token()
        print(" done")
    except Exception as e:
        print(" error")
        typer.echo(f"Authentication error: {str(e)}", err=True)
        raise typer.Exit(1)

    # Check if the script exists and has valid extension
    if not os.path.exists(script):
        typer.echo(f"Error: Script '{script}' not found", err=True)
        raise typer.Exit(1)

    file_extension = os.path.splitext(script)[1].lower()
    if file_extension not in [".py", ".ipynb"]:
        typer.echo("Error: Only .py and .ipynb files are supported", err=True)
        raise typer.Exit(1)

    # delete the tasknode_deploy folder if it already exists
    if os.path.exists("tasknode_deploy"):
        try:
            shutil.rmtree("tasknode_deploy")
        except Exception as e:
            typer.echo(f"Error removing existing deploy folder: {str(e)}", err=True)
            raise typer.Exit(1)

    # create a new folder called tasknode_deploy
    print("Creating deploy folder... ", end="", flush=True)
    try:
        os.makedirs("tasknode_deploy", exist_ok=True)
        print(" done")
    except Exception as e:
        typer.echo(f"Error creating deploy folder: {str(e)}", err=True)
        raise typer.Exit(1)

    # Define patterns to exclude
    exclude_patterns = {
        "tasknode_deploy.zip",
        "tasknode_deploy",
        ".git",
        "node_modules",
        "__pycache__",
        ".env",
        "venv",
        ".venv",
        ".idea",
        ".vscode",
        "dist",
        "build",
    }

    print("Copying files... ", end="", flush=True)
    try:
        for root, dirs, files in os.walk('.', topdown=True):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_patterns]
            
            for file in files:
                src_path = os.path.join(root, file)
                if should_copy(src_path, exclude_patterns):
                    # Convert source path to relative path
                    rel_path = os.path.relpath(src_path, '.')
                    dst_path = os.path.join('tasknode_deploy', rel_path)
                    
                    # Create destination directory if it doesn't exist
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    
                    # Copy the file
                    shutil.copy2(src_path, dst_path)
    except Exception as e:
        typer.echo(f"Error copying files: {str(e)}", err=True)
        raise typer.Exit(1)

    # get a list of installed packages
    requirements = [
        f"{dist.key}=={dist.version}"
        for dist in pkg_resources.working_set
        if "tasknode" not in dist.key.lower()
    ]

    # write the filtered results to a file called requirements.txt
    with open("tasknode_deploy/requirements-tasknode.txt", "w") as f:
        f.write("\n".join(requirements))
    print(" done")

    print("Getting system info... ", end="", flush=True)
    # find out which version of python is being used
    python_version = sys.version.split()[0]

    # Determine the OS type (Windows/Mac/Linux)
    os_type = platform.system()

    run_info = {
        "python_version": f"Python {python_version}",
        "os_info": os_type,
        "script": script,
    }

    # write the run_info to a file called run_info.json
    with open("tasknode_deploy/run_info.json", "w") as f:
        json.dump(run_info, f)
    print(" done")

    # get the size of the tasknode_deploy folder
    unzipped_mb = get_folder_size("tasknode_deploy")

    # zip the tasknode_deploy folder
    create_zip("tasknode_deploy", "tasknode_deploy.zip")

    # Get zip file size using Python's os.path.getsize()
    zipped_mb = os.path.getsize("tasknode_deploy.zip") / (1024 * 1024)  # Convert bytes to MB

    print("")
    print(f"Deployment size unzipped: {unzipped_mb:.2f} MB")
    print(f"Deployment size zipped: {zipped_mb:.2f} MB\n")

    # Check if the folder size is greater than 300MB
    if unzipped_mb > 300:
        typer.echo("Error: TaskNode only supports deployments up to 300MB.", err=True)
        raise typer.Exit(1)

    try:
        print("Uploading code to S3... ", end="", flush=True)
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
        try:
            if os.path.exists("tasknode_deploy"):
                shutil.rmtree("tasknode_deploy")
            if os.path.exists("tasknode_deploy.zip"):
                os.remove("tasknode_deploy.zip")
        except Exception as e:
            typer.echo(
                f"Warning: Error during cleanup: {str(e)}", err=True
            )


def should_copy(path, exclude_patterns):
    # Use os.path.normpath to handle Windows paths correctly
    path = os.path.normpath(path)
    # Use os.path.split instead of string split for cross-platform compatibility
    parts = path.split(os.sep)
    if any(part in exclude_patterns for part in parts):
        return False
    return not path.endswith(('.pyc', '.pyo', '.pyd', '.egg-info'))

def list_jobs(offset: int = 0):
    """
    List your TaskNode jobs and their statuses.
    """
    # Get authentication token
    print("Getting authentication token... ", end="", flush=True)
    try:
        access_token = get_valid_token()
        print(" done")
    except Exception as e:
        print(" error")
        typer.echo(f"Authentication error: {str(e)}", err=True)
        raise typer.Exit(1)

    limit = 20
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

        # If there are more jobs available, show the command to see the next page
        if end_index < total_job_count:
            next_offset = offset + limit
            print(
                f"To see the next page, run: `tasknode list-jobs --offset {next_offset}`"
            )

    except requests.exceptions.RequestException as e:
        typer.echo(f"Failed to fetch jobs: {str(e)}", err=True)
        raise typer.Exit(1)

def get_folder_size(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            total_size += os.path.getsize(filepath)
    return total_size / (1024 * 1024)  # Convert to MB

def create_zip(source_path, output_path):
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_path)
                zipf.write(file_path, arcname)
