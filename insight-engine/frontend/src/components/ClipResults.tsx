"use client";

import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel";
import { AspectRatio } from "@/components/ui/aspect-ratio";

interface Clip {
  url: string;
  title: string;
}

interface ClipResultsProps {
  clips: Clip[];
  isLoading: boolean;
}

const mockClips: Clip[] = [
    { url: "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4", title: "Clip 1" },
    { url: "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4", title: "Clip 2" },
    { url: "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4", title: "Clip 3" },
    { url: "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackOnStreetAndDirt.mp4", title: "Clip 4" },
    { url: "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4", title: "Clip 5" },
];


export function ClipResults({ clips = mockClips, isLoading }: ClipResultsProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
            <p className="text-lg font-semibold">Extracting clips...</p>
            <p className="text-sm text-muted-foreground">Please wait a moment.</p>
        </div>
      </div>
    );
  }

  if (!clips || clips.length === 0) {
    return (
        <div className="flex items-center justify-center h-full">
            <div className="text-center text-muted-foreground">
                <p>No clips to display.</p>
                <p className="text-sm">Select a video and enter a query to find clips.</p>
            </div>
        </div>
    );
  }

  return (
    <Card className="h-full flex flex-col">
      <CardHeader>
        <CardTitle>Extracted Clips</CardTitle>
      </CardHeader>
      <CardContent className="flex-grow flex items-center justify-center">
        <Carousel className="w-full max-w-md">
          <CarouselContent>
            {clips.map((clip, index) => (
              <CarouselItem key={index}>
                <div className="p-1">
                    <AspectRatio ratio={16 / 9}>
                        <video controls src={clip.url} className="rounded-lg w-full h-full object-cover" />
                    </AspectRatio>
                    <p className="text-center text-sm font-medium mt-2">{clip.title}</p>
                </div>
              </CarouselItem>
            ))}
          </CarouselContent>
          <CarouselPrevious />
          <CarouselNext />
        </Carousel>
      </CardContent>
    </Card>
  );
}