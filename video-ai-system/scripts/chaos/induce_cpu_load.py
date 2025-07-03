import multiprocessing
import time
import argparse

def cpu_burner():
    """
    A simple function to burn CPU cycles.
    """
    while True:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Induce CPU load.")
    parser.add_argument("--processes", type=int, default=1, help="Number of processes to use for load generation.")
    parser.add_argument("--duration", type=int, default=60, help="Duration to run the load test in seconds.")
    args = parser.parse_args()

    print("Starting CPU load generation...")
    print(f"This will run for {args.duration} seconds. Press Ctrl+C to stop early.")
    
    num_processes = args.processes
    print(f"Using {num_processes} process(es) to generate load.")

    processes = []
    for _ in range(num_processes):
        p = multiprocessing.Process(target=cpu_burner)
        p.start()
        processes.append(p)
        
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print("\nLoad generation interrupted early.")
    finally:
        print("\nStopping CPU load generation...")
        for p in processes:
            p.terminate()
            p.join()
        print("All processes terminated.")
