"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ClipResults } from "@/components/ClipResults";
import { Separator } from "@/components/ui/separator";

interface ClipExtractionProps {
  videoId: string | null;
}

export function ClipExtraction({ videoId }: ClipExtractionProps) {
  const [query, setQuery] = React.useState("");
  const [isLoading, setIsLoading] = React.useState(false);
  const [clips, setClips] = React.useState<any[]>([]);

  const handleExtractClips = async () => {
    if (!videoId || !query) {
      // You might want to show a toast or a message to the user
      return;
    }

    setIsLoading(true);
    // In a real application, you would make an API call here.
    // For now, we'll just simulate a delay.
    setTimeout(() => {
      // Mock data for now
      const mockClips = [
        { url: "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4", title: `Clips for "${query}" 1` },
        { url: "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4", title: `Clips for "${query}" 2` },
      ];
      setClips(mockClips);
      setIsLoading(false);
    }, 2000);
  };

  return (
    <div className="flex flex-col h-full space-y-4">
      <div className="flex w-full max-w-sm items-center space-x-2">
        <Input
          type="text"
          placeholder="e.g., 'logos', 'cars', 'a person smiling'"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={!videoId || isLoading}
        />
        <Button 
            onClick={handleExtractClips} 
            disabled={!videoId || !query || isLoading}
        >
          Extract Clips
        </Button>
      </div>
      <Separator />
      <div className="flex-grow">
        <ClipResults clips={clips} isLoading={isLoading} />
      </div>
    </div>
  );
}