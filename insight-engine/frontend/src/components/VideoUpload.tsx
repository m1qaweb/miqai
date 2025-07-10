"use client";

import { useState, ChangeEvent, Dispatch, SetStateAction } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";

interface VideoUploadProps {
  onUploadSuccess: Dispatch<SetStateAction<string | null>>;
}

export function VideoUpload({ onUploadSuccess }: VideoUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
      setUploadProgress(0);
      onUploadSuccess(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file first.");
      return;
    }

    setIsUploading(true);
    setError(null);
    setUploadProgress(0);
    onUploadSuccess(null);

    try {
      const response = await axios.post(
        "http://localhost:8000/uploads/request-url/",
        {
          file_name: file.name,
          content_type: file.type,
        }
      );

      const { upload_url, video_uri } = response.data;

      if (!upload_url || !video_uri) {
        throw new Error("Failed to get upload URL from the server.");
      }

      await axios.put(upload_url, file, {
        headers: {
          "Content-Type": file.type,
        },
        onUploadProgress: (progressEvent) => {
          const { loaded, total } = progressEvent;
          if (total) {
            const percent = Math.round((loaded * 100) / total);
            setUploadProgress(percent);
          }
        },
      });

      onUploadSuccess(video_uri);
      setFile(null); 
    } catch (err: any) {
      console.error("Upload failed:", err);
      setError(
        err.response?.data?.detail ||
          "An error occurred during the upload. Please try again."
      );
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="w-full max-w-md p-6 mx-auto space-y-6 border rounded-lg shadow-md bg-card text-card-foreground">
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-bold">Upload Your Video</h1>
        <p className="text-muted-foreground">
          Select a video file to upload to the processing engine.
        </p>
      </div>
      <div className="space-y-4">
        <div className="grid w-full max-w-sm items-center gap-1.5">
          <Label htmlFor="video-file">Video File</Label>
          <Input
            id="video-file"
            type="file"
            accept="video/*"
            onChange={handleFileChange}
            disabled={isUploading}
          />
        </div>
        <Button
          onClick={handleUpload}
          disabled={!file || isUploading}
          className="w-full"
        >
          {isUploading ? `Uploading... ${uploadProgress}%` : "Upload"}
        </Button>
      </div>

      {isUploading && (
        <div className="space-y-2">
          <Label>Upload Progress</Label>
          <Progress value={uploadProgress} className="w-full" />
        </div>
      )}

      {error && (
        <div
          className="p-4 text-sm text-red-700 bg-red-100 border border-red-400 rounded-lg"
          role="alert"
        >
          <span className="font-medium">Error:</span> {error}
        </div>
      )}
    </div>
  );
}