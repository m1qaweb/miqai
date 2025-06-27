#!/bin/sh

# Print out the environment for debugging
echo "--- Environment Variables ---"
printenv
echo "---------------------------"

echo "--- Python Path ---"
echo $PYTHONPATH
echo "-------------------"

echo "--- System Path ---"
python -c "import sys; print(sys.path)"
echo "-------------------"

# Execute the main application
# exec uvicorn video_ai_system.main:app --host 0.0.0.0 --port 8000

# Keep the container running for debugging
tail -f /dev/null