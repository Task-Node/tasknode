# TaskNode CLI 🚀

> **Note**: TaskNode is currently in beta. While fully functional, you may encounter occasional issues. Please report any bugs on our GitHub issues page.

A powerful command-line tool that lets you run Python scripts in the cloud with zero infrastructure setup.

## ✨ Features

- **Zero Configuration**: Just install and run - we handle all the cloud setup
- **Dependency Management**: Automatic detection and packaging of project dependencies
- **Cross-Platform**: Works on Linux, macOS, and Windows

## 🔧 Installation

```bash
pip install tasknode
```

For the latest development version:

```bash
git clone https://github.com/tasknode/tasknode-cli.git
cd tasknode-cli
pip install -e .
```

## 🚀 Quick Start

```bash
# Submit a script to run in the cloud
tasknode submit script.py

# Get help and see all commands
tasknode help
```

## 📦 What Gets Uploaded?

When you submit a script, TaskNode automatically:
- 📁 Packages your project directory
- 🔍 Excludes development folders (.git, venv, __pycache__, etc.)
- 📝 Captures dependencies in requirements-tasknode.txt
- ℹ️ Records Python version and system information
- 🔒 Securely uploads everything to our cloud infrastructure
