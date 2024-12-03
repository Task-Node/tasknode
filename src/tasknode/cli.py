import json
import os
import requests
import subprocess
import typer
import keyring
from typing import Optional

app = typer.Typer(no_args_is_help=True)

API_URL = "https://api-dev.tasknode.dev"  # Backend API URL
SERVICE_NAME = "tasknode-cli"


def show_available_commands(ctx: typer.Context, value: bool):
    if value:
        typer.echo("\n📋 Available Commands\n")
        
        typer.echo("🔑 Account Management:")
        typer.echo("  • signup     Sign up for a TaskNode account")
        typer.echo("  • login      Log in to your TaskNode account")
        typer.echo("  • logout     Log out of your TaskNode account")
        
        typer.echo("\n🚀 Core Functions:")
        typer.echo("  • submit     Submit a Python script to be run in the cloud")
        
        typer.echo("\nℹ️  Help:")
        typer.echo("  • help       Show help for the TaskNode CLI")
        typer.echo("")  # Add a newline
        raise typer.Exit()


@app.callback()
def callback(
    ctx: typer.Context,
    help: bool = typer.Option(
        None, "--help", "-h", is_eager=True, callback=show_available_commands
    ),
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
    script: str = typer.Argument(
        ...,
        help="The Python script to run (relative to the current directory, for example 'script.py' or 'path/to/script.py')",
    ),
):
    """
    Submit a Python script to be run in the cloud.
    """
    # Get authentication token
    try:
        access_token = get_valid_token()
    except keyring.errors.KeyringError as e:
        typer.echo(f"Authentication error: {str(e)}", err=True)
        raise typer.Exit(1)

    # Check if the script exists
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
        line for line in result.stdout.splitlines() if not "tasknode" in line.lower()
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

    run_info = {
        "python_version": python_version.stdout.strip(),
        "os_info": os_type,
        "script": script,
    }

    # write the run_info to a file called run_info.json
    with open("tasknode_deploy/run_info.json", "w") as f:
        json.dump(run_info, f)

    # zip the tasknode_deploy folder
    subprocess.run(["zip", "-r", "tasknode_deploy.zip", "tasknode_deploy/"])

    # Update the API request to include authentication
    try:
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

        typer.echo("Successfully uploaded code! 🚀")

    except requests.exceptions.RequestException as e:
        typer.echo(f"Upload failed: {str(e)}", err=True)
        raise typer.Exit(1)
    finally:
        # Clean up temporary files
        subprocess.run(["rm", "-rf", "tasknode_deploy", "tasknode_deploy.zip"])


@app.command()
def login(
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    """
    Log in to your TaskNode account.
    """
    try:
        response = requests.post(
            f"{API_URL}/api/v1/users/login",
            json={"email": email, "password": password},
        )

        # Check if response contains an error message
        if response.status_code == 401:
            typer.echo(f"Login failed: Invalid credentials. If you forgot your password, you can reset it using 'tasknode reset-password'. To sign up, use 'tasknode signup'.", err=True)
            raise typer.Exit(1)
        if response.status_code != 200:
            error_data = response.json()
            if "detail" in error_data:
                typer.echo(f"Login failed: {error_data['detail']}", err=True)
                raise typer.Exit(1)
            
        tokens = response.json()

        # Store tokens securely
        keyring.set_password(SERVICE_NAME, "access_token", tokens["access_token"])
        keyring.set_password(SERVICE_NAME, "id_token", tokens["id_token"])
        keyring.set_password(SERVICE_NAME, "refresh_token", tokens["refresh_token"])

        typer.echo("Successfully logged in! 🎉")

    except requests.exceptions.RequestException as e:
        typer.echo(f"Login failed: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def logout():
    """
    Log out of your TaskNode account.
    """
    try:
        keyring.delete_password(SERVICE_NAME, "access_token")
        keyring.delete_password(SERVICE_NAME, "id_token")
        keyring.delete_password(SERVICE_NAME, "refresh_token")
        typer.echo("Successfully logged out!")
    except keyring.errors.PasswordDeleteError:
        typer.echo("Already logged out!")


def refresh_tokens() -> Optional[str]:
    """
    Attempt to refresh the access token using the refresh token.
    Returns the new access token if successful, None otherwise.
    """
    try:
        refresh_token = keyring.get_password(SERVICE_NAME, "refresh_token")
        if not refresh_token:
            return None

        response = requests.post(
            f"{API_URL}/api/v1/users/refresh-token",
            json={"refresh_token": refresh_token}
        )
        response.raise_for_status()
        tokens = response.json()

        # Store new tokens
        keyring.set_password(SERVICE_NAME, "access_token", tokens["access_token"])
        keyring.set_password(SERVICE_NAME, "id_token", tokens["id_token"])
        
        return tokens["access_token"]
    except Exception:
        return None

def get_valid_token() -> str:
    """
    Get a valid access token or raise an error if not possible.
    """
    access_token = keyring.get_password(SERVICE_NAME, "access_token")
    if not access_token:
        typer.echo("Please login first using 'tasknode login'", err=True)
        raise typer.Exit(1)

    # Try to use the token
    response = requests.get(
        f"{API_URL}/api/v1/users/verify-token",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    
    if response.status_code == 401:  # Unauthorized - token might be expired
        new_token = refresh_tokens()
        if new_token:
            return new_token
        typer.echo("Session expired. Please login again using 'tasknode login'", err=True)
        raise typer.Exit(1)
        
    return access_token


if __name__ == "__main__":
    app()
