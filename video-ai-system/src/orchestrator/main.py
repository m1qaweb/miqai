import time

if __name__ == "__main__":
    print("Orchestrator service started...")
    try:
        while True:
            # This is a placeholder for the main orchestrator loop.
            # In the future, this will poll for tasks, manage workflows,
            # and coordinate with other services.
            time.sleep(1)
    except KeyboardInterrupt:
        print("Orchestrator service stopping.")