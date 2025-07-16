"use client";

import { useStore } from "@/lib/store";
import { VideoUpload } from "@/components/VideoUpload";
import SummarizationChat from "@/components/SummarizationChat";

export default function Home() {
  const { videoId, setVideoId } = useStore();

  const handleUploadSuccess = (id: string) => {
    setVideoId(id);
  };

  return (
    <main className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-8 p-8">
      <div className="flex flex-col gap-8">
        <h1 className="text-3xl font-bold">AI Playground: Summarization</h1>
        <VideoUpload
          onUploadSuccess={handleUploadSuccess}
          onUploadStart={() => setVideoId(null)}
          onUploadReset={() => setVideoId(null)}
        />
      </div>
      <div className="flex flex-col h-[calc(100vh-8rem)]">
        <SummarizationChat videoId={videoId} />
      </div>
    </main>
  );
}
