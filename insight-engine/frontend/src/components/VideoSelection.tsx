"use client";

import * as React from "react";
import { Check, ChevronsUpDown } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";

// Hardcoded list of videos for now
const videos = [
  { video_id: "video1", title: "A Day in the Life of a Software Engineer" },
  { video_id: "video2", title: "Unboxing the Latest Tech Gadgets" },
  { video_id: "video3", title: "How to Cook the Perfect Steak" },
  { video_id: "video4", title: "Exploring the Mountains of Switzerland" },
  { video_id: "video5", title: "The Ultimate Guide to Productivity Hacks" },
];

interface VideoSelectionProps {
  onSelectVideo: (videoId: string) => void;
}

export function VideoSelection({ onSelectVideo }: VideoSelectionProps) {
  const [open, setOpen] = React.useState(false);
  const [value, setValue] = React.useState("");

  return (
    <div className="w-full">
        <h2 className="text-lg font-semibold mb-2">Select a Video</h2>
        <p className="text-sm text-muted-foreground mb-4">
            Choose a video from the list to start extracting clips.
        </p>
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
            <Button
                variant="outline"
                role="combobox"
                aria-expanded={open}
                className="w-full justify-between"
            >
                {value
                ? videos.find((video) => video.video_id === value)?.title
                : "Select video..."}
                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
            </Button>
            </PopoverTrigger>
            <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
            <Command>
                <CommandInput placeholder="Search video..." />
                <CommandEmpty>No video found.</CommandEmpty>
                <CommandGroup>
                    <ScrollArea className="h-72">
                        {videos.map((video) => (
                        <CommandItem
                            key={video.video_id}
                            value={video.video_id}
                            onSelect={(currentValue: string) => {
                                const selectedValue = currentValue === value ? "" : currentValue;
                                setValue(selectedValue);
                                onSelectVideo(selectedValue);
                                setOpen(false);
                            }}
                        >
                            <Check
                            className={cn(
                                "mr-2 h-4 w-4",
                                value === video.video_id ? "opacity-100" : "opacity-0"
                            )}
                            />
                            {video.title}
                        </CommandItem>
                        ))}
                    </ScrollArea>
                </CommandGroup>
            </Command>
            </PopoverContent>
        </Popover>
    </div>
  );
}