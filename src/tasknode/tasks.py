from datetime import datetime
import json
import os
import requests
import pkg_resources
import platform
from rich import print
from rich.prompt import Confirm
from rich.table import Table
import shutil
import sys
import typer
import zipfile
from zoneinfo import ZoneInfo
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeRemainingColumn,
)

from tasknode.auth import get_valid_token
from tasknode.constants import API_URL
from tasknode.utils import format_file_size, format_time


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
    try:
        access_token = get_valid_token()
    except Exception as e:
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

    deploy_just_script = Confirm.ask(
        "\nIs this a standalone script (i.e., it does not depend on other files in this directory for config or data)?\n"
        "[cyan]•[/cyan] Yes = deploy only the script [cyan](default)[/cyan]\n"
        "[cyan]•[/cyan] No = deploy entire directory\n",
        default=True,
    )

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
        if deploy_just_script:
            # Copy only the script file, preserving its relative path
            rel_path = os.path.relpath(script, ".")
            dst_path = os.path.join("tasknode_deploy", rel_path)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)  # Create subdirectories if needed
            shutil.copy2(script, dst_path)
        else:
            # Copy entire directory (existing behavior)
            for root, dirs, files in os.walk(".", topdown=True):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in exclude_patterns]

                for file in files:
                    src_path = os.path.join(root, file)
                    try:
                        if should_copy(src_path, exclude_patterns):
                            rel_path = os.path.relpath(src_path, ".")
                            dst_path = os.path.join("tasknode_deploy", rel_path)
                            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                            shutil.copy2(src_path, dst_path)
                    except PermissionError:
                        typer.echo(f"Skipping file due to permission error: {src_path}", err=True)

    except Exception as e:
        typer.echo(f"Error copying files: {str(e)}", err=True)
        raise typer.Exit(1)
    print(" done")

    requirements = []
    requirements_file = "requirements.txt"
    if os.path.exists(requirements_file):
        use_requirements_file = Confirm.ask(
            f"\nA {requirements_file} file was found. Would you like to use that to handle dependencies?\n"
            "[cyan]•[/cyan] Yes = use requirements.txt file [cyan](default)[/cyan]\n"
            "[cyan]•[/cyan] No = use current environment's installed packages (like pip freeze)\n",
            default=True,
        )
        if use_requirements_file:
            print(f"Using {requirements_file} for dependencies... ", end="", flush=True)
            with open(requirements_file, "r") as f:
                requirements = f.readlines()
            print(" done")

    if not requirements:
        # get a list of installed packages
        print("Gathering current environment's packages... ", end="", flush=True)
        requirements = [
            f"{dist.key}=={dist.version}" for dist in pkg_resources.working_set if "tasknode" not in dist.key.lower()
        ]
        print(" done")

    # write the filtered results to a file called requirements-tasknode.txt
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


def should_copy(path, exclude_patterns):
    # Use os.path.normpath to handle Windows paths correctly
    path = os.path.normpath(path)
    # Use os.path.split instead of string split for cross-platform compatibility
    parts = path.split(os.sep)
    if any(part in exclude_patterns for part in parts):
        return False
    return not path.endswith((".pyc", ".pyo", ".pyd", ".egg-info"))


def jobs(offset: int = 0):
    """
    List your TaskNode jobs and their statuses.
    """
    # Get authentication token
    try:
        access_token = get_valid_token()
    except Exception as e:
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
        table.add_column("Index", style="bold")
        table.add_column("Job ID", style="cyan")
        table.add_column("Status", style="magenta")
        table.add_column("Created at", style="green")
        table.add_column("Updated at", style="yellow")
        table.add_column("Runtime", style="blue")

        # Add rows to the table
        for index, job in enumerate(jobs_data["jobs"], start=offset + 1):
            created_dt = datetime.fromisoformat(job["created_at"]).replace(tzinfo=ZoneInfo("UTC"))
            updated_dt = datetime.fromisoformat(job["updated_at"]).replace(tzinfo=ZoneInfo("UTC"))

            created_at = created_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S%z")
            updated_at = updated_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S%z")

            table.add_row(
                str(index),
                str(job["id"]),
                job["status"],
                created_at,
                updated_at,
                format_time(job["runtime"]),
            )

        # Print the table
        print("")
        print(table)

        # If there are more jobs available, show the command to see the next page
        if end_index < total_job_count:
            next_offset = offset + limit
            print(f"To see the next page, run: `tasknode list-jobs --offset {next_offset}`")
            print("\nTo get details for a specific job, run: `tasknode job <job_id || index>`")
            print(
                "(for example `tasknode job 1` will get you the most recently created job and `tasknode job faa868f9-b0cb-4792-b176-64575dab86a7` will get you the job with that ID)\n"
            )

    except requests.exceptions.RequestException as e:
        typer.echo(f"Failed to fetch jobs: {str(e)}", err=True)
        raise typer.Exit(1)


def generate_sample(
    destination: str = typer.Argument(".", help="The destination directory to copy the notebook to"),
):
    """
    Generate a sample Jupyter notebook in the specified directory.
    The notebook is copied from the TaskNode repository's test.ipynb.
    """
    # GitHub raw content URL for the sample notebook
    SAMPLE_NOTEBOOK_URL = "https://raw.githubusercontent.com/Task-Node/tasknode/main/sample.ipynb"
    OUTPUT_FILENAME = "sample.ipynb"

    # Construct the full path to the destination
    destination_path = os.path.join(destination, OUTPUT_FILENAME)

    try:
        # Download the notebook content
        response = requests.get(SAMPLE_NOTEBOOK_URL)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Create the destination directory if it doesn't exist
        os.makedirs(destination, exist_ok=True)

        # Write the notebook content to the destination
        with open(destination_path, "wb") as f:
            f.write(response.content)

        typer.echo(f"✨ Sample notebook has been generated at '{destination_path}'")
    except requests.RequestException as e:
        typer.echo(f"❌ Error downloading the sample notebook: {e}")
    except Exception as e:
        typer.echo(f"❌ An error occurred: {e}")


def get_folder_size(path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            total_size += os.path.getsize(filepath)
    return total_size / (1024 * 1024)  # Convert to MB


def create_zip(source_path, output_path):
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_path)
                zipf.write(file_path, arcname)


def get_job_details(job_id: str, tail_lines: int = 10):
    """
    Get details of a specific TaskNode job using either a job ID (UUID) or job index number.
    """
    try:
        access_token = get_valid_token()
    except Exception as e:
        typer.echo(f"Authentication error: {str(e)}", err=True)
        raise typer.Exit(1)

    try:
        # Fetch job details using either UUID or index number
        response = requests.get(
            f"{API_URL}/api/v1/jobs/get/{job_id}",
            params={"tail_lines": tail_lines},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code == 404:
            typer.echo(f"Job not found", err=True)
            raise typer.Exit(1)

        response.raise_for_status()
        job_data = response.json()

        created_dt = datetime.fromisoformat(job_data["created_at"]).replace(tzinfo=ZoneInfo("UTC"))
        updated_dt = datetime.fromisoformat(job_data["updated_at"]).replace(tzinfo=ZoneInfo("UTC"))

        created_at = created_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S%z")
        updated_at = updated_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S%z")

        # Display job details in a table
        details_table = Table(show_header=False)
        details_table.add_column("Field", style="bold")
        details_table.add_column("Value")

        details_table.add_row("Status", f"[plum3]{job_data['status'].upper()}[/plum3]")
        details_table.add_row("Job ID", job_data["id"])
        details_table.add_row("Runtime", format_time(job_data["runtime"]))
        details_table.add_row("Created", created_at)
        details_table.add_row("Updated", updated_at)

        print(details_table)
        print("")

        # Display files associated with the job
        if job_data["files"]:
            table = Table(title="Generated Files")
            table.add_column("File Name", style="cyan")
            table.add_column("File Size", style="magenta")
            table.add_column("Timestamp", style="green")

            for file in job_data["files"]:
                file_size = format_file_size(file["file_size"])
                table.add_row(file["file_name"], file_size, file["file_timestamp"])

            print(table)
        else:
            print("No generated files associated with this job.")

        has_output_log = job_data.get("output_log_tail", []) and len(job_data["output_log_tail"]) > 0
        has_error_log = job_data.get("error_log_tail", []) and len(job_data["error_log_tail"]) > 0
        has_generated_files = job_data.get("files", []) and len(job_data["files"]) > 0

        # Add log tail outputs
        if has_output_log:
            print(f"\n[bold]Output log tail (last {tail_lines} lines):[/bold]")
            print("[dim cyan]─" * 50)
            for line in job_data["output_log_tail"]:
                print(f"  {line}")
            print("[dim cyan]─" * 50)

        if has_error_log:
            print(f"\n[bold red]Error log tail (last {tail_lines} lines):[/bold red]")
            print("[dim red]─" * 50)
            for line in job_data["error_log_tail"]:
                print(f"  {line}")
            print("[dim red]─" * 50)

        if not has_output_log and not has_error_log:
            print("\nNo log output available (check back soon)\n")

        if (
            job_data["status"] == "completed"
            or job_data["status"] == "failed"
            and (has_generated_files or has_output_log or has_error_log)
        ):
            print(
                f"\nTo download files associated with this job, run: `[blue]tasknode download {job_data['id']}[/blue]`\n"
            )

    except requests.exceptions.RequestException as e:
        typer.echo(f"Failed to fetch job details: {str(e)}", err=True)
        raise typer.Exit(1)


def download_job_files(job_identifier: str, destination: str = "."):
    """
    Download all files associated with a specific job.
    """
    try:
        access_token = get_valid_token()
    except Exception as e:
        typer.echo(f"Authentication error: {str(e)}", err=True)
        raise typer.Exit(1)

    try:
        # Get signed URLs for all files
        response = requests.get(
            f"{API_URL}/api/v1/jobs/{job_identifier}/download_urls",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if response.status_code == 404:
            typer.echo(f"Job not found", err=True)
            raise typer.Exit(1)

        response.raise_for_status()
        data = response.json()

        if not data["files"]:
            print("\n[yellow]No files available for download.[/yellow]")
            return

        # Create progress bars
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.completed:.0f}/{task.total}"),
            TimeRemainingColumn(),
        ) as progress:
            overall_task = progress.add_task("[cyan]Overall progress", total=len(data["files"]), completed=0)

            for file in data["files"]:
                filename = file["filename"]
                base_path = os.path.join(destination, filename)

                # Check if file exists and generate new name if needed
                final_path = base_path
                counter = 2
                if os.path.exists(final_path):
                    print(f"[yellow]Note:[/yellow] File '{base_path}' already exists")
                    while os.path.exists(final_path):
                        name, ext = os.path.splitext(base_path)
                        final_path = f"{name}_{counter}{ext}"
                        counter += 1
                    print(f"[yellow]      Saving as '{final_path}' instead[/yellow]")

                # Create file task before getting size
                file_task = progress.add_task(f"[magenta]Downloading {filename}", total=100)

                response = requests.get(file["signedUrl"], stream=True)
                response.raise_for_status()

                total_size = int(response.headers.get("content-length", 0))
                block_size = 1024 * 1024  # 1MB chunks
                downloaded = 0

                with open(final_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=block_size):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            # Update progress as percentage and force refresh
                            percentage = min((downloaded / total_size) * 100, 100)
                            progress.update(file_task, completed=percentage, refresh=True)

                # Complete the file task
                progress.update(file_task, completed=100, refresh=True)
                # Update overall progress
                progress.update(overall_task, advance=1, refresh=True)

        print("\n[green]✓[/green] All files downloaded successfully!")

    except requests.exceptions.RequestException as e:
        typer.echo(f"\nFailed to download files: {str(e)}", err=True)
        raise typer.Exit(1)
