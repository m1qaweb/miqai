"use client";

import { useState, FormEvent, Dispatch, SetStateAction } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { VideoUpload } from "@/components/VideoUpload";
import { SummarizationDisplay } from "@/components/SummarizationDisplay";
import ClipCarousel from "@/components/ClipCarousel";
import { Separator } from "@/components/ui/separator";
import { Video, FileCode, Bot, Loader2 } from "lucide-react";

function VideoQueryUI({ videoUri }: { videoUri: string | null }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("idle");
  const [response, setResponse] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!videoUri || !query) {
      setError("A video URI and a query are required.");
      return;
    }

    setStatus("processing");
    setResponse("");
    setError("");

    try {
      const res = await fetch("http://localhost:8000/video-query/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ gcs_uri: videoUri, query }),
      });

      if (!res.ok || !res.body) {
        const errorText = await res.text();
        throw new Error(
          `API Error: ${res.status} ${res.statusText} - ${errorText}`
        );
      }

      setStatus("streaming");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const dataLines = chunk
          .split("\n")
          .filter((line) => line.startsWith("data: "));

        for (const line of dataLines) {
          try {
            const jsonData = JSON.parse(line.substring(5));
            if (jsonData.error) {
              throw new Error(jsonData.error);
            }
            if (jsonData.token) {
              setResponse((prev) => prev + jsonData.token);
            }
          } catch (e) {
            console.error("Failed to parse stream data:", line);
          }
        }
      }
    } catch (e: any) {
      setError(e.message);
      setStatus("error");
    } finally {
      setStatus((prev) => (prev === "streaming" ? "done" : prev));
    }
  };

  const isLoading = status === "processing" || status === "streaming";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Query Your Video</CardTitle>
        <CardDescription>
          Ask a question about the content of the video you just uploaded.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            placeholder="Video GCS URI"
            value={videoUri || "Upload a video above to get a URI"}
            disabled
          />
          <Input
            placeholder="Ask a question (e.g., What is the main topic of the video?)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={isLoading || !videoUri}
          />
          <Button type="submit" disabled={isLoading || !videoUri}>
            {isLoading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {status === "processing"
              ? "Processing..."
              : status === "streaming"
              ? "Streaming..."
              : "Process Video"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const [uploadedVideoUri, setUploadedVideoUri] = useState<string | null>(
    null
  );

  return (
    <div className="grid min-h-screen w-full lg:grid-cols-[280px_1fr]">
      <div className="hidden border-r bg-gray-100/40 lg:block dark:bg-gray-800/40">
        <div className="flex flex-col h-full max-h-screen gap-2">
          <div className="flex h-[60px] items-center border-b px-6">
            <a className="flex items-center gap-2 font-semibold" href="#">
              <FileCode className="w-6 h-6" />
              <span>Insight Engine</span>
            </a>
          </div>
          <div className="flex-1 py-2 overflow-auto">
            <nav className="grid items-start px-4 text-sm font-medium">
              <a
                className="flex items-center gap-3 px-3 py-2 text-gray-900 transition-all rounded-lg bg-gray-100 hover:text-gray-900 dark:bg-gray-800 dark:text-gray-50 dark:hover:text-gray-50"
                href="#"
              >
                <Video className="w-4 h-4" />
                Video Analysis
              </a>
            </nav>
          </div>
        </div>
      </div>
      <div className="flex flex-col">
        <header className="flex h-14 lg:h-[60px] items-center gap-4 border-b bg-gray-100/40 px-6 dark:bg-gray-800/40">
          <div className="flex-1 w-full">
            <h1 className="text-lg font-semibold">Video Analysis</h1>
          </div>
        </header>
        <main className="flex flex-col flex-1 gap-4 p-4 md:gap-8 md:p-6">
          <VideoUpload onUploadSuccess={setUploadedVideoUri} />
          <Separator className="my-4" />
          <ClipCarousel videoUri={uploadedVideoUri || ""} />
          <Separator className="my-4" />
          <VideoQueryUI videoUri={uploadedVideoUri} />
          <Separator className="my-4" />
          <SummarizationDisplay videoUri={uploadedVideoUri || ""} />
        </main>
      </div>
    </div>
  );
}
