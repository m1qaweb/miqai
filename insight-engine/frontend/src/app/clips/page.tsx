"use client";

import * as React from "react";
import { VideoSelection } from "@/components/VideoSelection";
import { ClipExtraction } from "@/components/ClipExtraction";
import { Separator } from "@/components/ui/separator";

export default function ClipsPage() {
  const [selectedVideoId, setSelectedVideoId] = React.useState<string | null>(
    null
  );

  const handleVideoSelect = (videoId: string) => {
    setSelectedVideoId(videoId);
  };

  return (
    <div className="h-screen w-full flex flex-col">
        <header className="p-4 border-b">
            <h1 className="text-2xl font-bold">Clip Extraction Playground</h1>
            <p className="text-sm text-muted-foreground">
                Select a video, enter a query, and extract relevant clips.
            </p>
        </header>
        <div className="flex-grow grid md:grid-cols-12 gap-4 p-4 overflow-hidden">
            <aside className="md:col-span-4 lg:col-span-3 xl:col-span-2 h-full overflow-y-auto">
                <VideoSelection onSelectVideo={handleVideoSelect} />
            </aside>
            <div className="hidden md:block">
                <Separator orientation="vertical" />
            </div>
            <main className="md:col-span-7 lg:col-span-8 xl:col-span-9 h-full overflow-y-auto">
                <ClipExtraction videoId={selectedVideoId} />
            </main>
        </div>
    </div>
  );
}