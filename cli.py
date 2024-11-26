import json
import os
import requests
import subprocess
import typer
import keyring
import webbrowser
from datetime import datetime, timedelta
import click

app = typer.Typer()

API_URL = "https://api-dev.tasknode.xyz"  # Backend API URL
SERVICE_NAME = "tasknode-cli"

@app.command()
def login(
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True)
):
    """
    Log in to TaskNode using email and password
    """
    try:
        response = requests.post(
            f"{API_URL}/api/v1/users/login",
            json={"email": email, "password": password}
        )
        response.raise_for_status()
        
        # Store tokens securely
        tokens = response.json()
        keyring.set_password(SERVICE_NAME, "access_token", tokens["access_token"])
        keyring.set_password(SERVICE_NAME, "refresh_token", tokens["refresh_token"])
        keyring.set_password(SERVICE_NAME, "token_expiry", 
            (datetime.now() + timedelta(seconds=tokens["expires_in"])).isoformat()
        )
        
        typer.echo("Successfully logged in! 🎉")
    except requests.exceptions.RequestException as e:
        typer.echo(f"Login failed: {str(e)}", err=True)
        raise typer.Exit(1)

def get_auth_header():
    """
    Helper function to get the authorization header with valid token
    """
    access_token = keyring.get_password(SERVICE_NAME, "access_token")
    if not access_token:
        typer.echo("\nYou need to be logged in to continue.")
        options = ["Login", "Create new account"]
        
        for idx, option in enumerate(options, 1):
            typer.echo(f"{idx}. {option}")
            
        choice = click.prompt(
            "\nPlease select an option",
            type=click.Choice(['1', '2']),
            show_choices=False
        )
        
        if choice == '1':
            login()
        else:
            signup()
            
        # Try getting the token again after login/signup
        access_token = keyring.get_password(SERVICE_NAME, "access_token")
        if not access_token:
            typer.echo("Authentication failed. Please try again.", err=True)
            raise typer.Exit(1)
    
    # TODO: Add refresh token logic here
    return {"Authorization": f"Bearer {access_token}"}

@app.command()
def submit(script: str, args: str = ""):
    """
    Submit a Python script to be run in the cloud.
    """
    # Add authentication header to future API calls
    auth_header = get_auth_header()
    
    # create a new folder called tasknode_deploy
    subprocess.run(["mkdir", "tasknode_deploy"])

    # remove the tasknode_deploy folder if it already exists
    subprocess.run(["rm", "-rf", "tasknode_deploy"])

    # Copy everything in the current directory into tasknode_deploy folder, excluding specific directories
    subprocess.run([
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
        "tasknode_deploy/"
    ])

    # get the results of running pip freeze
    result = subprocess.run(["pip", "freeze"], capture_output=True, text=True)

    # write the results to a file called requirements.txt
    with open("tasknode_deploy/requirements-tasknode.txt", "w") as f:
        f.write(result.stdout)

    # find out which version of python is being used
    python_version = subprocess.run(["python", "--version"], capture_output=True, text=True)
    
    # Determine the OS type (Windows/Mac/Linux)
    if os.name == 'nt':
        os_type = "Windows"
    else:
        os_info = subprocess.run(["uname"], capture_output=True, text=True)
        os_type = "Mac" if "Darwin" in os_info.stdout else "Linux"
    
    env_info = {
        "python_version": python_version.stdout.strip(),
        "os_info": os_type
    }

    # write the env_info to a file called env_info.json
    with open("tasknode_deploy/env_info.json", "w") as f:
        json.dump(env_info, f)

    # zip the tasknode_deploy folder
    subprocess.run(["zip", "-r", "tasknode_deploy.zip", "tasknode_deploy/"])
    

@app.command()
def signup(
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
    confirm_password: str = typer.Option(..., prompt=True, hide_input=True)
):
    """
    Create a new TaskNode account
    """
    if password != confirm_password:
        typer.echo("Passwords do not match!", err=True)
        raise typer.Exit(1)

    try:
        response = requests.post(
            f"{API_URL}/api/v1/users/signup",
            json={"email": email, "password": password}
        )
        response.raise_for_status()
        
        # Store tokens securely (assuming the signup endpoint returns tokens)
        tokens = response.json()
        keyring.set_password(SERVICE_NAME, "access_token", tokens["access_token"])
        keyring.set_password(SERVICE_NAME, "refresh_token", tokens["refresh_token"])
        keyring.set_password(SERVICE_NAME, "token_expiry", 
            (datetime.now() + timedelta(seconds=tokens["expires_in"])).isoformat()
        )
        
        typer.echo("Account created successfully! 🎉")
    except requests.exceptions.RequestException as e:
        typer.echo(f"Signup failed: {str(e)}", err=True)
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
