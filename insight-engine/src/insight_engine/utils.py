import os


def verify_pythonpath() -> None:
    """Print the current PYTHONPATH environment variable."""
    print("PYTHONPATH:", os.environ.get("PYTHONPATH", "Not set"))
