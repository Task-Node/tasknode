# TaskNode CLI 🚀

> **Note**: TaskNode is currently in beta. While fully functional, you may encounter occasional issues. Please report any bugs on our GitHub issues page.

A powerful command-line tool that lets you run Python scripts in the cloud with zero infrastructure setup.

## ✨ Features

- **Zero Configuration**: Just install and run - we handle all the cloud setup
- **Dependency Management**: Automatic detection and packaging of project dependencies
- **Cross-Platform**: Works on Linux, macOS, and Windows

## 🚀 Get started in 3 minutes

First, install TaskNode:

```bash
pip install tasknode
```

Optionally, generate a script to run:

```bash
cat << 'EOF' > script.py
with open("outputs.txt", "w") as file:
    for number in range(1, 11):
        file.write(f"{number}\n")
print("Numbers 1-10 have been written to outputs.txt")
EOF
```

Then, submit a script to run in the cloud:

```bash
tasknode submit script.py
```

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
