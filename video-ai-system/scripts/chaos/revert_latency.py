import os
import fileinput

# The path to the pipeline service file
pipeline_service_path = os.path.join(
    os.path.dirname(__file__), 
    '..', '..', 'src', 'video_ai_system', 'services', 'pipeline_service.py'
)

# The line to remove
line_to_remove = "        import time; time.sleep(5) # CHAOS: Introduce artificial latency"

# Read the file content
with open(pipeline_service_path, 'r') as f:
    lines = f.readlines()

# Check if the file has been modified
already_modified = any(line_to_remove in line for line in lines)

if not already_modified:
    print("Latency modification not found. Skipping.")
else:
    # Remove the line in memory
    new_lines = [line for line in lines if line_to_remove not in line]

    # Write the file back
    with open(pipeline_service_path, 'w') as f:
        f.writelines(new_lines)
    print("Latency modification reverted from pipeline_service.py")