import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  useDeleteWikiAsset,
  useUploadWikiAsset,
  useWikiAssets,
} from "@/hooks/useWiki";
import type { WikiAsset } from "@/types";
import { FileImage, FileText, Search, Trash2, Upload } from "lucide-react";

function isImageAsset(asset: WikiAsset): boolean {
  return asset.content_type.startsWith("image/");
}

function buildMarkdownForAsset(asset: WikiAsset): string {
  if (isImageAsset(asset)) {
    return `![${asset.filename}](${asset.content_url})`;
  }
  return `[${asset.filename}](${asset.content_url})`;
}

function AssetPreview({ asset }: { asset: WikiAsset }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!isImageAsset(asset)) return;
    const controller = new AbortController();
    let objectUrl = "";

    void fetch(asset.content_url, {
      headers: {
        Authorization: localStorage.getItem("access_token")
          ? `Bearer ${localStorage.getItem("access_token")}`
          : "",
        "X-Tenant-ID": localStorage.getItem("tenant_id") || "",
      },
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Failed preview");
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      })
      .catch(() => {
        setBlobUrl(null);
      });

    return () => {
      controller.abort();
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [asset]);

  if (!isImageAsset(asset)) {
    return (
      <div className="flex h-28 items-center justify-center rounded-md border border-border bg-muted/30 text-muted-foreground">
        <FileText size={22} />
      </div>
    );
  }

  if (!blobUrl) {
    return (
      <div className="flex h-28 items-center justify-center rounded-md border border-border bg-muted/30 text-xs text-muted-foreground">
        Loading...
      </div>
    );
  }

  return (
    <img
      alt={asset.filename}
      className="h-28 w-full rounded-md border border-border object-cover"
      src={blobUrl}
    />
  );
}

export function WikiAssetLibrary({
  canDelete,
  onClose,
  onInsert,
}: {
  canDelete: boolean;
  onClose: () => void;
  onInsert: (markdown: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const { data, isLoading } = useWikiAssets(query, page, 12);
  const uploadAsset = useUploadWikiAsset();
  const deleteAsset = useDeleteWikiAsset();

  useEffect(() => {
    setPage(1);
  }, [query]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await uploadAsset.mutateAsync(file);
    event.target.value = "";
  };

  const handleDelete = async (asset: WikiAsset) => {
    if (!canDelete) return;
    if (!confirm(`Delete asset "${asset.filename}"?`)) return;
    await deleteAsset.mutateAsync(asset.id);
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="flex max-h-[85vh] w-full max-w-5xl flex-col overflow-hidden">
        <div className="border-b border-border p-5">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h3 className="text-lg font-semibold">Media Library</h3>
              <p className="text-sm text-muted-foreground">
                Search, upload, and insert reusable assets.
              </p>
            </div>
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
            <div className="relative">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                className="pl-8"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search assets..."
                value={query}
              />
            </div>
            <label className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-md border border-border bg-background px-4 text-sm font-medium hover:bg-accent">
              <Upload size={14} />
              {uploadAsset.isPending ? "Uploading..." : "Upload Asset"}
              <input
                className="hidden"
                onChange={handleFileUpload}
                type="file"
              />
            </label>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-5">
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading assets...</p>
          ) : data && data.items.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {data.items.map((asset) => (
                <Card key={asset.id} className="p-3">
                  <AssetPreview asset={asset} />
                  <div className="mt-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{asset.filename}</p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(asset.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <Badge variant="secondary">
                        {isImageAsset(asset) ? (
                          <span className="inline-flex items-center gap-1">
                            <FileImage size={12} />
                            Image
                          </span>
                        ) : (
                          "File"
                        )}
                      </Badge>
                    </div>
                    <div className="mt-3 flex items-center justify-between gap-2">
                      <Button
                        size="sm"
                        onClick={() => {
                          onInsert(buildMarkdownForAsset(asset));
                          onClose();
                        }}
                      >
                        Insert
                      </Button>
                      {canDelete && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => void handleDelete(asset)}
                        >
                          <Trash2 size={14} />
                        </Button>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No assets found.</p>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-border p-4">
          <p className="text-sm text-muted-foreground">
            {data ? `${data.total} assets` : "0 assets"}
          </p>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={page === 1}
              onClick={() => setPage((current) => current - 1)}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={page >= totalPages}
              onClick={() => setPage((current) => current + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
