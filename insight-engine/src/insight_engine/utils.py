import os


def verify_pythonpath():
    print("PYTHONPATH:", os.environ.get("PYTHONPATH", "Not set"))
