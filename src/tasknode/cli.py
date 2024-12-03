import json
import os
import requests
import subprocess
import typer
import keyring
import webbrowser
from datetime import datetime, timedelta
import click

app = typer.Typer(no_args_is_help=True)

API_URL = "https://api-dev.tasknode.dev"  # Backend API URL
SERVICE_NAME = "tasknode-cli"

def show_available_commands(ctx: typer.Context, value: bool):
    if value:
        typer.echo("\nAvailable commands:")
        typer.echo("  submit    Submit a Python script to be run in the cloud")
        typer.echo("  help      Show help for the TaskNode CLI")
        raise typer.Exit()

@app.callback()
def callback(
    ctx: typer.Context,
    help: bool = typer.Option(None, "--help", "-h", is_eager=True, callback=show_available_commands),
):
    """
    TaskNode CLI - Run your Python scripts in the cloud
    """
    pass

@app.command()
def help():
    """
    Show help for the TaskNode CLI.
    """
    show_available_commands(None, True)

@app.command()
def submit(
    script: str = typer.Argument(..., help="The Python script to run (relative to the current directory, for example 'script.py' or 'path/to/script.py')"),
):
    """
    Submit a Python script to be run in the cloud.
    """
    if not os.path.exists(script):
        typer.echo(f"Error: Script '{script}' not found", err=True)
        raise typer.Exit(1)

    # create a new folder called tasknode_deploy
    subprocess.run(["mkdir", "tasknode_deploy"])

    # remove the tasknode_deploy folder if it already exists
    subprocess.run(["rm", "-rf", "tasknode_deploy"])

    # Copy everything in the current directory into tasknode_deploy folder, excluding specific directories
    subprocess.run(
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
        ]
    )

    # get the results of running pip freeze and filter out tasknode packages
    result = subprocess.run(["pip", "freeze"], capture_output=True, text=True)
    requirements = [
        line for line in result.stdout.splitlines() 
        if not 'tasknode' in line.lower()
    ]

    # write the filtered results to a file called requirements.txt
    with open("tasknode_deploy/requirements-tasknode.txt", "w") as f:
        f.write("\n".join(requirements))

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

    run_info = {"python_version": python_version.stdout.strip(), "os_info": os_type, "script": script}

    # write the run_info to a file called run_info.json
    with open("tasknode_deploy/run_info.json", "w") as f:
        json.dump(run_info, f)

    # zip the tasknode_deploy folder
    subprocess.run(["zip", "-r", "tasknode_deploy.zip", "tasknode_deploy/"])

    # Get signed URL from API
    try:
        response = requests.get(
            f"{API_URL}/api/v1/jobs/get_zip_upload_url",
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

        typer.echo("Successfully uploaded code! 🚀")

    except requests.exceptions.RequestException as e:
        typer.echo(f"Upload failed: {str(e)}", err=True)
        raise typer.Exit(1)
    finally:
        # Clean up temporary files
        subprocess.run(["rm", "-rf", "tasknode_deploy", "tasknode_deploy.zip"])


if __name__ == "__main__":
    app()
