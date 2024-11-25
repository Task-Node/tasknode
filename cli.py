import json
import os
import requests
import subprocess
import typer

app = typer.Typer()

API_URL = "http://localhost:8000/execute"  # Backend API URL

@app.command()
def submit(script: str, args: str = ""):
    """
    Submit a Python script to be run in the cloud.
    """
    
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
    

if __name__ == "__main__":
    app()
