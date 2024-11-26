# TaskNode CLI

A command-line tool for running Python scripts in the cloud.

## Installation

```bash
pip install tasknode
```

To install the development version from source, clone the repository and run:

```bash
pip install -e .
```


After this setup, you can:
- Use `pip install .` to install the package
- Use `pip install -e .` for development installation
- Run the CLI with just `tasknode submit script.py` from anywhere
- Distribute your package to PyPI using `python -m build` and `python -m twine upload dist/*`

Note: The `server/config/test.py` file seems to be part of a different component (server-side), so I didn't include it in the CLI package structure.

Would you like me to explain any part of this setup in more detail?