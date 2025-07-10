"use client";

import { useState, useEffect, useRef } from "react";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Skeleton } from "./ui/skeleton";

// Updated Clip type to include status and job details
export type Clip = {
  jobId: string;
  status: "processing" | "available" | "failed";
  start_time: number;
  end_time: number;
  video_uri?: string;
  description: string;
};

type ClipCarouselProps = {
  videoUri: string;
};

// A simple skeleton loader for clips being processed
const ClipSkeleton = () => (
  <Card className="min-w-[300px]">
    <CardHeader>
      <Skeleton className="h-[168px] w-full rounded-md" />
    </CardHeader>
    <CardContent>
      <Skeleton className="h-5 w-20 mb-2" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-1/2 mt-1" />
    </CardContent>
  </Card>
);

const ClipCarousel = ({ videoUri }: ClipCarouselProps) => {
  const [clips, setClips] = useState<Clip[]>([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const handleExtractClips = async () => {
    setIsExtracting(true);
    setClips([]);
    setError(null);

    // In a real app, these might come from user input or another API
    const clipsToRequest = [
      { start_time: 0, end_time: 10, prompt: "A person is talking about the project's architecture." },
      { start_time: 15, end_time: 25, prompt: "A code snippet is shown on the screen." },
      { start_time: 30, end_time: 45, prompt: "The presenter discusses future plans for the application." },
    ];

    try {
      const response = await fetch("http://localhost:8000/analysis/extract-clips/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_uri: videoUri, clips: clipsToRequest }),
      });

      if (response.status !== 202) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to start clip extraction.");
      }

      const { job_ids } = await response.json();

      const initialClips: Clip[] = clipsToRequest.map((clip, index) => ({
        jobId: job_ids[index],
        status: "processing",
        start_time: clip.start_time,
        end_time: clip.end_time,
        description: clip.prompt,
      }));

      setClips(initialClips);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unknown error occurred.");
      setIsExtracting(false);
    }
  };

  useEffect(() => {
    // Function to poll job statuses
    const pollJobs = async () => {
      setClips(currentClips => {
        const processingClips = currentClips.filter(c => c.status === 'processing');
        
        if (processingClips.length === 0) {
          if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
          setIsExtracting(false);
          return currentClips;
        }

        const newClips = [...currentClips];
        let changed = false;

        processingClips.forEach(async (clip) => {
          try {
            const res = await fetch(`http://localhost:8000/analysis/job/${clip.jobId}`);
            const data = await res.json();
            
            const clipIndex = newClips.findIndex(c => c.jobId === clip.jobId);

            if (res.status === 200 && data.status === 'complete') {
              newClips[clipIndex] = { ...clip, status: 'available', video_uri: data.result };
              changed = true;
            } else if (res.status === 500 || data.status === 'failed') {
              newClips[clipIndex] = { ...clip, status: 'failed' };
              changed = true;
            }
          } catch (e) {
            const clipIndex = newClips.findIndex(c => c.jobId === clip.jobId);
            newClips[clipIndex] = { ...clip, status: 'failed' };
            changed = true;
          }
        });

        if (changed) {
            // This update is tricky inside an async loop. A better pattern would be
            // to Promise.all the fetches and then set state once.
            // For this implementation, we'll rely on the interval re-running.
            // A more robust solution might use a library like SWR or React Query.
        }
        return newClips;
      });
    };

    const hasProcessingJobs = clips.some(c => c.status === 'processing');

    if (hasProcessingJobs && !pollingIntervalRef.current) {
      pollingIntervalRef.current = setInterval(pollJobs, 3000);
    }

    // Cleanup interval on component unmount
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [clips]);

  return (
    <div className="w-full">
      <div className="flex items-center space-x-4">
        <h2 className="text-2xl font-bold tracking-tight">Video Clips</h2>
        <Button onClick={handleExtractClips} disabled={isExtracting || !videoUri}>
          {isExtracting ? "Extracting..." : "Extract Clips"}
        </Button>
      </div>

      {error && <p className="text-red-500 mt-4">Error: {error}</p>}

      {(isExtracting || clips.length > 0) && (
        <div className="relative mt-4">
          <div className="flex space-x-4 overflow-x-auto pb-4">
            {clips.map((clip) => {
              if (clip.status === "processing") {
                return <ClipSkeleton key={clip.jobId} />;
              }
              if (clip.status === "available" && clip.video_uri) {
                return (
                  <Card key={clip.jobId} className="min-w-[300px]">
                    <CardHeader>
                      <video controls src={clip.video_uri} className="rounded-md" />
                    </CardHeader>
                    <CardContent>
                      <CardTitle className="text-lg">Clip</CardTitle>
                      <CardDescription className="mt-2">{clip.description}</CardDescription>
                      <p className="text-sm text-gray-500 mt-2">
                        {clip.start_time}s - {clip.end_time}s
                      </p>
                    </CardContent>
                  </Card>
                );
              }
              if (clip.status === "failed") {
                 return (
                  <Card key={clip.jobId} className="min-w-[300px] border-red-500">
                     <CardContent className="pt-6">
                       <p className="text-red-500">Failed to generate clip.</p>
                       <p className="text-sm text-gray-500">{clip.description}</p>
                     </CardContent>
                  </Card>
                 )
              }
              return null;
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default ClipCarousel;