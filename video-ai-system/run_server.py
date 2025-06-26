import uvicorn
import sys
from pathlib import Path

if __name__ == "__main__":
    # Add the 'src' directory to the Python path
    src_path = Path(__file__).parent / "src"
    sys.path.insert(0, str(src_path))
    
    print(f"Starting server, running from: {Path.cwd()}")
    print(f"Python path includes: {src_path}")
    
    # Run the application
    uvicorn.run(
        "video_ai_system.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False  # Disable reload for stability
    )