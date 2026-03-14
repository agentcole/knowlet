import { useEffect, useMemo, useState, type ComponentType } from "react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { useSearchAll } from "@/hooks/useSearch";
import type { SearchResult, SearchSourceType } from "@/types";
import { BookOpen, FileText, Mic, Search as SearchIcon } from "lucide-react";

const typeConfig: Record<
  SearchSourceType,
  { label: string; icon: ComponentType<{ size?: number; className?: string }> }
> = {
  wiki_page: { label: "Wiki", icon: BookOpen },
  document: { label: "Document", icon: FileText },
  document_chunk: { label: "Document Chunk", icon: FileText },
  meeting: { label: "Meeting", icon: Mic },
};

function resultHref(result: SearchResult): string {
  if (result.source_type === "wiki_page") {
    return `/wiki?pageId=${result.source_id}`;
  }
  if (result.source_type === "meeting") {
    return `/meetings?meetingId=${result.source_id}`;
  }
  return "/documents";
}

function typeLabel(result: SearchResult): string {
  return typeConfig[result.source_type]?.label ?? "Content";
}

export function SearchPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");

  useEffect(() => {
    const trimmed = query.trim();
    const handle = setTimeout(() => setDebouncedQuery(trimmed), 250);
    return () => clearTimeout(handle);
  }, [query]);

  const { data, isLoading } = useSearchAll(debouncedQuery);

  const results = useMemo(() => data?.results ?? [], [data?.results]);

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Search</h1>
        <p className="mt-1 text-muted-foreground">
          Search across wiki pages, documents, and meeting transcripts.
        </p>
      </div>

      <div className="relative mb-6 max-w-2xl">
        <SearchIcon
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search all content..."
          className="pl-9"
        />
      </div>

      {debouncedQuery.length < 2 ? (
        <p className="text-sm text-muted-foreground">
          Enter at least 2 characters to search.
        </p>
      ) : isLoading ? (
        <p className="text-sm text-muted-foreground">Searching...</p>
      ) : results.length === 0 ? (
        <p className="text-sm text-muted-foreground">No results found.</p>
      ) : (
        <div className="space-y-3">
          {results.map((result) => {
            const Icon = typeConfig[result.source_type]?.icon;
            return (
              <Card key={`${result.source_type}-${result.source_id}`} className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      {Icon ? <Icon size={16} className="text-muted-foreground" /> : null}
                      <h3 className="truncate text-sm font-semibold">{result.title}</h3>
                    </div>
                    {result.snippet && (
                      <p className="mt-2 text-xs text-muted-foreground">{result.snippet}</p>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <Badge variant="secondary">{typeLabel(result)}</Badge>
                    <Link
                      to={resultHref(result)}
                      className="text-xs font-medium text-primary hover:underline"
                    >
                      Open
                    </Link>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
