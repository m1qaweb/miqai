"use client";

import { useEffect, useRef, useState } from "react";
import DOMPurify from "dompurify";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useStore } from "@/lib/store";

interface SummarizationDisplayProps {
  videoUri: string;
}

export const SummarizationDisplay: React.FC<SummarizationDisplayProps> = ({ videoUri }) => {
  const { summary, setSummary, isStreaming, setIsStreaming } = useStore();
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const handleSummarizeClick = () => {
    if (!videoUri) {
      setError("A video URI must be provided to generate a summary.");
      return;
    }

    setError(null);
    setSummary("");
    setIsStreaming(true);

    // The backend endpoint accepts the video_uri as a query parameter for the GET request.
    const url = `http://localhost:8000/analysis/summarize/?video_uri=${encodeURIComponent(videoUri)}`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            if (message.error) {
                setError(`Error from server: ${message.error}`);
                setIsStreaming(false);
                eventSource.close();
            } else if (message.chunk) {
                setSummary(summary + message.chunk);
            }
        } catch (e) {
            // Handle cases where the final message might not be JSON
            if (event.data.includes("END_OF_STREAM")) {
                setIsStreaming(false);
                eventSource.close();
            } else {
                 console.warn("Received non-JSON message:", event.data);
            }
        }
    };

    eventSource.onerror = (err) => {
      console.error("EventSource failed:", err);
      setError("Connection to the summarization service failed. The service might be down or unreachable. See browser console for details.");
      setIsStreaming(false);
      eventSource.close();
    };
  };

  // Cleanup effect to close the connection when the component unmounts or the videoUri changes.
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, [videoUri]);

  return (
    <div className="w-full p-4 border rounded-lg">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-semibold mb-2 sm:mb-0">Video Summary</h2>
            <Button onClick={handleSummarizeClick} disabled={isStreaming || !videoUri}>
                {isStreaming ? "Generating Summary..." : "Generate Summary"}
            </Button>
        </div>

      {error && <p className="text-red-500 mt-4">{error}</p>}

      {(summary || isStreaming) && (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Live Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className="text-sm text-muted-foreground whitespace-pre-wrap"
              dangerouslySetInnerHTML={{
                __html: DOMPurify.sanitize(summary + (isStreaming ? '<span class="animate-pulse">...</span>' : "")),
              }}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
};