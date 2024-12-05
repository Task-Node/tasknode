# TaskNode 🔄

[![PyPI version](https://badge.fury.io/py/tasknode.svg)](https://pypi.org/project/tasknode/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

> **Note**: TaskNode is currently in beta. While fully functional, you may encounter occasional issues. Please report any bugs on our GitHub issues page.

Do you ever:

- Keep your computer on all night just to run a script?
- Run scripts that would benefit from a much faster internet connection?
- Have too many scripts running at a time?

TaskNode is a powerful command-line tool that lets you run Python scripts asynchronously in the cloud with zero infrastructure setup. Submit a task, and we'll handle the rest.

## ✨ Features

- **Zero Configuration**: Just install and run - we handle all the cloud setup
- **Dependency Management**: Automatic detection and packaging of project dependencies
- **Cross-Platform**: Works on Linux, macOS, and Windows
- **Notifications**: Get an email when your task is complete

## 🚀 Get started in 2 minutes

First, install TaskNode:

```bash
pip install tasknode
```

Optionally, generate a sample Jupyter notebook to run:

```bash
tasknode generate-sample  # copies sample.ipynb to current directory
```

Then, submit a Jupyter notebook to run in the cloud:

```bash
tasknode submit sample.ipynb
# or
tasknode submit your_script.py
```

## Jupyter notebooks

TaskNode also supports Jupyter notebooks. Just submit your notebook (e.g., `tasknode submit notebook.ipynb`), and we'll convert it to a Python script and run it for you.

## Get help and see all commands

```bash
tasknode help
```

## 📦 What Gets Uploaded?

When you submit a script, TaskNode automatically:
- 📁 Packages your project directory
- 🔍 Excludes development folders (.git, venv, __pycache__, etc.)
- 📝 Captures dependencies in requirements-tasknode.txt
- ℹ️ Records Python version and system information
- 🔒 Securely uploads everything to our cloud infrastructure


## FAQ

### How does TaskNode handle my files?

TaskNode securely uploads your files to our cloud infrastructure and deletes them after your task is complete. If the task fails, the files are retained for 24 hours in case you need to re-run the task.

Any outputs generated are retained for up to 72 hours, during which time you can download them.

### How does TaskNode handle my dependencies?

TaskNode automatically detects your dependencies and packages them in a separate file called `requirements-tasknode.txt`. This file is uploaded to our cloud infrastructure and installed when your task is run.

### How does TaskNode handle my Python version?

Right now, TaskNode runs on Docker containers with Python 3.12. Most Python 3 code will work without any changes, but we're working on adding support for other Python versions.


### Where is the data processed?

All data is processed in the AWS US East (N. Virginia) region.
