import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDropzone } from "react-dropzone";
import { meetingsApi } from "@/api/meetings";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Mic, Upload, Clock, Users } from "lucide-react";
import type { Meeting, Transcript } from "@/types";

export function MeetingsPage() {
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploadTitle, setUploadTitle] = useState("");

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["meetings", page],
    queryFn: () => meetingsApi.list(page).then((r) => r.data),
    refetchInterval: 5000,
  });

  const { data: transcript } = useQuery({
    queryKey: ["transcript", selectedId],
    queryFn: () => meetingsApi.getTranscript(selectedId!).then((r) => r.data),
    enabled: !!selectedId,
  });

  const onDrop = useCallback(
    async (files: File[]) => {
      if (files[0]) {
        const title = uploadTitle || files[0].name.replace(/\.[^/.]+$/, "");
        await meetingsApi.upload(files[0], title);
        setUploadTitle("");
        refetch();
      }
    },
    [uploadTitle, refetch]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "audio/*": [".wav", ".mp3", ".m4a", ".ogg", ".webm"] },
    maxFiles: 1,
  });

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return "—";
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="flex h-full">
      {/* List */}
      <div className="w-96 border-r border-border p-4 overflow-auto">
        <h2 className="text-xl font-bold mb-4">Meetings</h2>

        <Input
          placeholder="Meeting title (optional)"
          value={uploadTitle}
          onChange={(e) => setUploadTitle(e.target.value)}
          className="mb-2"
        />

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-4 text-center mb-4 cursor-pointer transition-colors ${
            isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
          }`}
        >
          <input {...getInputProps()} />
          <Upload size={24} className="mx-auto mb-2 text-muted-foreground" />
          <p className="text-xs text-muted-foreground">
            Drop audio file or click to browse
          </p>
        </div>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : !data?.items.length ? (
          <div className="text-center py-8 text-muted-foreground">
            <Mic size={32} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">No meetings yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {data.items.map((meeting) => (
              <Card
                key={meeting.id}
                className={`p-3 cursor-pointer transition-colors ${
                  selectedId === meeting.id ? "ring-2 ring-primary" : "hover:bg-accent/50"
                }`}
                onClick={() => setSelectedId(meeting.id)}
              >
                <p className="text-sm font-medium">{meeting.title}</p>
                <div className="flex items-center gap-3 mt-1">
                  <Badge
                    variant={meeting.status === "processed" ? "success" : meeting.status === "failed" ? "destructive" : "warning"}
                  >
                    {meeting.status}
                  </Badge>
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock size={12} /> {formatDuration(meeting.duration_seconds)}
                  </span>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Transcript viewer */}
      <div className="flex-1 overflow-auto p-8">
        {transcript ? (
          <div>
            <h2 className="text-xl font-bold mb-4">Transcript</h2>

            {transcript.summary && (
              <Card className="p-4 mb-6">
                <h3 className="font-semibold mb-2">Summary</h3>
                <p className="text-sm">{transcript.summary}</p>
              </Card>
            )}

            {transcript.action_items && transcript.action_items.length > 0 && (
              <Card className="p-4 mb-6">
                <h3 className="font-semibold mb-2">Action Items</h3>
                <ul className="list-disc list-inside text-sm space-y-1">
                  {transcript.action_items.map((item, i) => (
                    <li key={i}>
                      <strong>{item.assignee}</strong>: {item.task}
                      {item.deadline && <span className="text-muted-foreground"> (Due: {item.deadline})</span>}
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            {transcript.segments && transcript.segments.length > 0 ? (
              <div className="space-y-3">
                {transcript.segments.map((seg, i) => (
                  <div key={i} className="flex gap-3">
                    <div className="shrink-0">
                      <Badge variant="outline" className="text-xs">
                        {seg.speaker}
                      </Badge>
                      <p className="text-xs text-muted-foreground mt-1">
                        {Math.floor(seg.start / 60)}:{Math.round(seg.start % 60).toString().padStart(2, "0")}
                      </p>
                    </div>
                    <p className="text-sm">{seg.text}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="whitespace-pre-wrap text-sm">{transcript.full_text}</div>
            )}
          </div>
        ) : selectedId ? (
          <p className="text-muted-foreground">Loading transcript...</p>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <Mic size={48} className="mx-auto mb-3 opacity-50" />
              <p>Select a meeting to view its transcript</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
