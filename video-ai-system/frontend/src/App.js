import React, { useState, useEffect, useRef } from "react";
import "./App.css";

function App() {
  const [videos, setVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [frames, setFrames] = useState([]);
  const [currentFrame, setCurrentFrame] = useState(null);
  const [error, setError] = useState(null);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  // Fetch the list of processed videos on component mount
  useEffect(() => {
    const fetchVideos = async () => {
      try {
        const response = await fetch("/analytics/videos");
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setVideos(data.videos);
      } catch (e) {
        setError(`Failed to fetch videos: ${e.message}`);
        console.error(e);
      }
    };
    fetchVideos();
  }, []);

  // Fetch frame data when a video is selected
  useEffect(() => {
    if (!selectedVideo) return;

    const fetchFrames = async () => {
      try {
        setError(null);
        setFrames([]);
        setCurrentFrame(null);
        const response = await fetch(
          `/analytics/videos/${selectedVideo}/frames`
        );
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setFrames(data.frames);
        if (data.frames.length > 0) {
          setCurrentFrame(data.frames[0]);
        }
      } catch (e) {
        setError(
          `Failed to fetch frame data for ${selectedVideo}: ${e.message}`
        );
        console.error(e);
      }
    };
    fetchFrames();
  }, [selectedVideo]);

  // Draw bounding boxes when the current frame changes
  useEffect(() => {
    if (videoRef.current && canvasRef.current && currentFrame) {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d");

      const drawBoxes = () => {
        // Set canvas dimensions to match video
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        // Draw the current video frame onto the canvas
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        // Draw bounding boxes
        ctx.strokeStyle = "red";
        ctx.lineWidth = 2;
        ctx.font = "16px Arial";
        ctx.fillStyle = "red";

        currentFrame.detections.forEach((det) => {
          const [x1, y1, x2, y2] = det.box;
          const width = x2 - x1;
          const height = y2 - y1;
          ctx.strokeRect(x1, y1, width, height);
          ctx.fillText(
            `${det.label} (${det.confidence.toFixed(2)})`,
            x1,
            y1 > 10 ? y1 - 5 : y1 + 15
          );
        });
      };

      // When the video's time updates, find the corresponding frame data
      const handleTimeUpdate = () => {
        const currentTime = video.currentTime;
        const frame = frames.find(
          (f) => Math.abs(f.timestamp - currentTime) < 0.1
        );
        if (frame && frame.frame_number !== currentFrame.frame_number) {
          setCurrentFrame(frame);
        }
      };

      video.addEventListener("timeupdate", handleTimeUpdate);

      // Initial draw
      if (video.readyState >= 2) {
        // HAVE_CURRENT_DATA
        drawBoxes();
      } else {
        video.onloadeddata = drawBoxes;
      }

      return () => {
        video.removeEventListener("timeupdate", handleTimeUpdate);
        video.onloadeddata = null;
      };
    }
  }, [currentFrame, frames]);

  const handleVideoSelect = (video) => {
    setSelectedVideo(video);
    if (videoRef.current) {
      // Assuming videos are served from a static path
      videoRef.current.src = `/static/videos/${video}`;
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Video AI Analysis Dashboard</h1>
      </header>
      {error && <div className="error-banner">{error}</div>}
      <div className="container">
        <div className="panel video-list-panel">
          <h2>Processed Videos</h2>
          <ul>
            {videos.map((video) => (
              <li
                key={video}
                onClick={() => handleVideoSelect(video)}
                className={selectedVideo === video ? "selected" : ""}
              >
                {video}
              </li>
            ))}
          </ul>
        </div>
        <div className="panel video-player-panel">
          <h2>Video Player</h2>
          <video
            ref={videoRef}
            controls
            muted
            playsInline
            className="video-player"
          ></video>
          {currentFrame && (
            <div className="frame-info">
              <p>Frame: {currentFrame.frame_number}</p>
              <p>Timestamp: {currentFrame.timestamp.toFixed(2)}s</p>
            </div>
          )}
        </div>
        <div className="panel detections-panel">
          <h2>Detections</h2>
          <canvas ref={canvasRef} className="detections-canvas"></canvas>
          {currentFrame && (
            <ul>
              {currentFrame.detections.map((det, index) => (
                <li key={index}>
                  {det.label} ({det.confidence.toFixed(2)}) - Box: [
                  {det.box.join(", ")}]
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
