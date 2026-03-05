import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useQueryClient } from "@tanstack/react-query";
import { useDocuments, useUploadDocument, useDeleteDocument } from "@/hooks/useDocuments";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Upload, Trash2, RefreshCw, FileText } from "lucide-react";
import { documentsApi } from "@/api/documents";
import { useAuthStore } from "@/store/auth";
import type {
  Document,
  DocumentWikiWorkflow,
  WikiPlacementAction,
} from "@/types";

const statusVariant: Record<string, "default" | "secondary" | "success" | "destructive" | "warning"> = {
  uploaded: "secondary",
  processing: "warning",
  processed: "success",
  failed: "destructive",
};

const wikiStateVariant: Record<
  string,
  "default" | "secondary" | "success" | "destructive" | "warning"
> = {
  processing: "warning",
  pending_approval: "warning",
  published: "success",
  failed: "destructive",
};

function deriveTitleFromFilename(filename: string): string {
  const base = filename.includes(".") ? filename.split(".").slice(0, -1).join(".") : filename;
  const normalized = base
    .replace(/[_\-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!normalized) return "Imported Content";
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function getWikiState(doc: Document): string {
  const metadata = doc.metadata as Record<string, unknown> | null;
  const workflow = metadata?.wiki_workflow as Record<string, unknown> | undefined;
  if (typeof workflow?.state === "string") {
    return workflow.state;
  }
  if (doc.status === "processed") {
    return "pending_approval";
  }
  if (doc.status === "failed") {
    return "failed";
  }
  return "processing";
}

export function DocumentsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useDocuments(page);
  const upload = useUploadDocument();
  const deleteDoc = useDeleteDocument();
  const { memberships, currentTenantId } = useAuthStore();
  const currentMembership = memberships.find((m) => m.tenant_id === currentTenantId);
  const canApproveWiki =
    currentMembership?.role === "owner" || currentMembership?.role === "admin";

  const [reviewDoc, setReviewDoc] = useState<Document | null>(null);
  const [workflow, setWorkflow] = useState<DocumentWikiWorkflow | null>(null);
  const [workflowLoading, setWorkflowLoading] = useState(false);
  const [workflowError, setWorkflowError] = useState("");
  const [placement, setPlacement] = useState({
    category_name: "",
    page_title: "",
    action: "create_new" as WikiPlacementAction,
  });
  const [revisionNote, setRevisionNote] = useState("");
  const [approving, setApproving] = useState(false);

  const onDrop = useCallback(
    (files: File[]) => {
      files.forEach((file) => upload.mutate(file));
    },
    [upload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
      "text/markdown": [".md"],
    },
  });

  const openReview = async (doc: Document) => {
    setReviewDoc(doc);
    setWorkflow(null);
    setWorkflowError("");
    setRevisionNote("");
    setWorkflowLoading(true);
    try {
      const { data: wf } = await documentsApi.getWikiWorkflow(doc.id);
      setWorkflow(wf);
      const suggestion = wf.suggestion || {
        category_name: "General",
        page_title: deriveTitleFromFilename(doc.filename),
        action: "create_new" as const,
      };
      setPlacement({
        category_name: suggestion.category_name,
        page_title: suggestion.page_title,
        action: suggestion.action,
      });
    } catch (err) {
      setWorkflowError(
        err instanceof Error ? err.message : "Failed to load wiki placement workflow",
      );
    } finally {
      setWorkflowLoading(false);
    }
  };

  const closeReview = () => {
    setReviewDoc(null);
    setWorkflow(null);
    setWorkflowError("");
    setRevisionNote("");
  };

  const approvePlacement = async () => {
    if (!reviewDoc) return;
    setApproving(true);
    setWorkflowError("");
    try {
      const { data: wf } = await documentsApi.approveWikiPlacement(reviewDoc.id, {
        placement,
        revision_note: revisionNote || undefined,
      });
      setWorkflow(wf);
      closeReview();
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["wiki-tree"] });
    } catch (err) {
      setWorkflowError(
        err instanceof Error ? err.message : "Failed to publish wiki placement",
      );
    } finally {
      setApproving(false);
    }
  };

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Documents</h1>
      </div>

      {/* Upload area */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center mb-6 cursor-pointer transition-colors ${
          isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
        }`}
      >
        <input {...getInputProps()} />
        <Upload size={40} className="mx-auto mb-3 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          {isDragActive
            ? "Drop files here..."
            : "Drag & drop files here, or click to browse"}
        </p>
        <p className="text-xs text-muted-foreground mt-1">PDF, DOCX, TXT, MD</p>
        <p className="text-xs text-muted-foreground mt-2">
          Uploads are indexed for chat, then require admin wiki approval before publishing.
        </p>
        {upload.isPending && <p className="text-sm text-primary mt-2">Uploading...</p>}
      </div>

      {/* Document list */}
      {isLoading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : !data?.items.length ? (
        <div className="text-center py-12 text-muted-foreground">
          <FileText size={48} className="mx-auto mb-3 opacity-50" />
          <p>No documents yet. Upload your first document above.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {data.items.map((doc) => {
            const wikiState = getWikiState(doc);
            return (
            <Card key={doc.id} className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3 min-w-0">
                <FileText size={20} className="text-muted-foreground shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{doc.filename}</p>
                  <p className="text-xs text-muted-foreground">
                    {doc.file_type.toUpperCase()} &middot; {new Date(doc.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={statusVariant[doc.status] || "secondary"}>{doc.status}</Badge>
                <Badge variant={wikiStateVariant[wikiState] || "secondary"}>
                  wiki: {wikiState.replace("_", " ")}
                </Badge>
                {canApproveWiki && doc.status === "processed" && wikiState !== "published" && (
                  <Button variant="outline" size="sm" onClick={() => openReview(doc)}>
                    Review Wiki
                  </Button>
                )}
                {doc.status === "failed" && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => documentsApi.reprocess(doc.id)}
                  >
                    <RefreshCw size={16} />
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => deleteDoc.mutate(doc.id)}
                >
                  <Trash2 size={16} />
                </Button>
              </div>
            </Card>
            );
          })}

          {/* Pagination */}
          {data.total > data.page_size && (
            <div className="flex justify-center gap-2 pt-4">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <span className="flex items-center text-sm text-muted-foreground">
                Page {page} of {Math.ceil(data.total / data.page_size)}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= Math.ceil(data.total / data.page_size)}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </div>
      )}

      {reviewDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-2xl p-6">
            <h2 className="text-xl font-semibold mb-2">Review Wiki Placement</h2>
            <p className="text-sm text-muted-foreground mb-4">
              {reviewDoc.filename}
            </p>

            {workflowLoading ? (
              <p className="text-sm text-muted-foreground">Loading suggestion...</p>
            ) : (
              <>
                {workflow?.suggestion && (
                  <div className="mb-4 rounded-md border border-border p-3 text-sm">
                    <p className="font-medium mb-1">LLM suggestion</p>
                    <p>
                      {workflow.suggestion.action} in <strong>{workflow.suggestion.category_name}</strong> /
                      <strong> {workflow.suggestion.page_title}</strong>
                    </p>
                    {workflow.suggestion.reasoning && (
                      <p className="text-muted-foreground mt-1">{workflow.suggestion.reasoning}</p>
                    )}
                  </div>
                )}

                {workflowError && (
                  <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                    {workflowError}
                  </div>
                )}

                <div className="grid grid-cols-1 gap-3 mb-4">
                  <div>
                    <label className="text-sm font-medium">Category</label>
                    <input
                      className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                      value={placement.category_name}
                      onChange={(e) =>
                        setPlacement((prev) => ({ ...prev, category_name: e.target.value }))
                      }
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Page Title</label>
                    <input
                      className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                      value={placement.page_title}
                      onChange={(e) =>
                        setPlacement((prev) => ({ ...prev, page_title: e.target.value }))
                      }
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">Action</label>
                    <select
                      className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                      value={placement.action}
                      onChange={(e) =>
                        setPlacement((prev) => ({
                          ...prev,
                          action: e.target.value as WikiPlacementAction,
                        }))
                      }
                    >
                      <option value="create_new">Create new page</option>
                      <option value="append">Append to existing page</option>
                      <option value="replace">Replace existing page</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-medium">Revision Note (optional)</label>
                    <textarea
                      className="mt-1 min-h-[80px] w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                      value={revisionNote}
                      onChange={(e) => setRevisionNote(e.target.value)}
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={closeReview} disabled={approving}>
                    Cancel
                  </Button>
                  <Button
                    onClick={approvePlacement}
                    disabled={
                      approving ||
                      !placement.category_name.trim() ||
                      !placement.page_title.trim()
                    }
                  >
                    {approving ? "Publishing..." : "Approve & Publish"}
                  </Button>
                </div>
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
