import os
import fileinput

# The path to the pipeline service file
pipeline_service_path = os.path.join(
    os.path.dirname(__file__), 
    '..', '..', 'src', 'video_ai_system', 'services', 'pipeline_service.py'
)

# The line to search for to insert the sleep
search_line = "def process_video(self, video_path: str, inference_id: str = None) -> PipelineOutput:"
# The line to add
add_line = "        import time; time.sleep(5) # CHAOS: Introduce artificial latency"

# Read the file content
with open(pipeline_service_path, 'r') as f:
    lines = f.readlines()

# Check if the file has already been modified
already_modified = any(add_line in line for line in lines)

if already_modified:
    print("Latency already introduced. Skipping.")
else:
    # Add the line in memory
    new_lines = []
    for line in lines:
        new_lines.append(line)
        if search_line in line:
            new_lines.append(add_line + '\n')

    # Write the file back
    with open(pipeline_service_path, 'w') as f:
        f.writelines(new_lines)
    print("Latency introduced into pipeline_service.py")