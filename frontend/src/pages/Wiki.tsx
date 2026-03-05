import { useEffect, useMemo, useState, type DragEvent } from "react";
import ReactMarkdown from "react-markdown";
import { useSearchParams } from "react-router-dom";
import {
  useWikiTree,
  useWikiPage,
  useWikiSearch,
  useCreateWikiPage,
  useCreateWikiCategory,
  useUpdateWikiCategory,
  useDeleteWikiCategory,
  useUpdateWikiPage,
  useDeleteWikiPage,
  useWikiRevisions,
  useRestoreWikiRevision,
  useReindexWiki,
} from "@/hooks/useWiki";
import { useQueryClient } from "@tanstack/react-query";
import { wikiApi } from "@/api/wiki";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import {
  BookOpen,
  FolderOpen,
  Search,
  Plus,
  Save,
  History,
  FolderPlus,
  Settings2,
  Trash2,
  ChevronDown,
  ChevronRight,
  ArrowDown,
  ArrowUp,
  RefreshCw,
} from "lucide-react";
import { useAuthStore } from "@/store/auth";
import type { WikiCategory } from "@/types";

type FlatCategory = {
  id: string;
  name: string;
  depth: number;
};

type DragPayload =
  | {
      type: "page";
      id: string;
      sourceCategoryId: string | null;
    }
  | {
      type: "category";
      id: string;
      sourceParentId: string | null;
    };

type DropTarget =
  | { type: "category"; id: string }
  | { type: "root" }
  | { type: "uncategorized" };

function dropTargetKey(target: DropTarget): string {
  if (target.type === "category") {
    return `category:${target.id}`;
  }
  return target.type;
}

function flattenCategories(categories: WikiCategory[], depth = 0): FlatCategory[] {
  const flat: FlatCategory[] = [];
  for (const category of categories) {
    flat.push({ id: category.id, name: category.name, depth });
    flat.push(...flattenCategories(category.children, depth + 1));
  }
  return flat;
}

function findCategoryById(categories: WikiCategory[], id: string): WikiCategory | null {
  for (const category of categories) {
    if (category.id === id) return category;
    const nested = findCategoryById(category.children, id);
    if (nested) return nested;
  }
  return null;
}

function findCategoryIdForPage(categories: WikiCategory[], pageId: string): string | null {
  for (const category of categories) {
    if (category.pages.some((page) => page.id === pageId)) {
      return category.id;
    }
    const nested = findCategoryIdForPage(category.children, pageId);
    if (nested) return nested;
  }
  return null;
}

function CategoryTree({
  categories,
  onSelectPage,
  selectedPageId,
  selectedCategoryId,
  onSelectCategory,
  onAddSubcategory,
  onEditCategory,
  canManageStructure,
  activeDropTarget,
  onDragStartCategory,
  onDragStartPage,
  onDropOnCategory,
  onDragEnterCategory,
  onDragLeaveCategory,
  onDragEnd,
  collapsedCategoryIds,
  onToggleCategoryCollapse,
  onMoveCategory,
  onMovePage,
}: {
  categories: WikiCategory[];
  onSelectPage: (id: string) => void;
  selectedPageId: string | null;
  selectedCategoryId: string | null;
  onSelectCategory: (id: string) => void;
  onAddSubcategory: (parentId: string) => void;
  onEditCategory: (categoryId: string) => void;
  canManageStructure: boolean;
  activeDropTarget: string | null;
  onDragStartCategory: (
    categoryId: string,
    parentId: string | null,
    event: DragEvent<HTMLDivElement>,
  ) => void;
  onDragStartPage: (
    pageId: string,
    categoryId: string | null,
    event: DragEvent<HTMLButtonElement>,
  ) => void;
  onDropOnCategory: (categoryId: string) => Promise<void>;
  onDragEnterCategory: (categoryId: string) => void;
  onDragLeaveCategory: (categoryId: string) => void;
  onDragEnd: () => void;
  collapsedCategoryIds: Record<string, boolean>;
  onToggleCategoryCollapse: (categoryId: string) => void;
  onMoveCategory: (
    categoryId: string,
    direction: "up" | "down",
    siblingCategoryIds: string[],
  ) => Promise<void>;
  onMovePage: (
    pageId: string,
    direction: "up" | "down",
    categoryId: string | null,
    siblingPageIds: string[],
  ) => Promise<void>;
}) {
  return (
    <div className="space-y-1">
      {categories.map((cat, categoryIndex) => {
        const isCollapsed = !!collapsedCategoryIds[cat.id];
        const hasChildren = cat.children.length > 0;
        const hasPages = cat.pages.length > 0;
        const hasContent = hasChildren || hasPages;
        const siblingCategoryIds = categories.map((category) => category.id);
        const siblingPageIds = cat.pages.map((page) => page.id);

        return (
          <div key={cat.id}>
          <div
            className={`group flex items-center gap-1 rounded px-2 py-1 text-sm ${
              selectedCategoryId === cat.id
                ? "bg-accent text-foreground"
                : "text-muted-foreground"
            } ${
              activeDropTarget === `category:${cat.id}`
                ? "border border-dashed border-primary/60 bg-primary/10 text-foreground"
                : ""
            }`}
            draggable={canManageStructure}
            onDragStart={(event) => onDragStartCategory(cat.id, cat.parent_id, event)}
            onDragEnd={onDragEnd}
            onDragOver={(event) => {
              if (!canManageStructure) return;
              event.preventDefault();
              event.stopPropagation();
              onDragEnterCategory(cat.id);
            }}
            onDragLeave={(event) => {
              if (!canManageStructure) return;
              event.stopPropagation();
              onDragLeaveCategory(cat.id);
            }}
            onDrop={(event) => {
              if (!canManageStructure) return;
              event.preventDefault();
              event.stopPropagation();
              void onDropOnCategory(cat.id);
            }}
          >
            {hasContent ? (
              <button
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded hover:bg-background"
                onClick={(event) => {
                  event.stopPropagation();
                  onToggleCategoryCollapse(cat.id);
                }}
                title={isCollapsed ? "Expand folder" : "Collapse folder"}
              >
                {isCollapsed ? (
                  <ChevronRight className="h-3.5 w-3.5 shrink-0" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5 shrink-0" />
                )}
              </button>
            ) : (
              <span className="inline-block h-6 w-6 shrink-0" />
            )}
            <button
              className="flex min-w-0 flex-1 items-center gap-1 text-left"
              onClick={() => onSelectCategory(cat.id)}
            >
              <FolderOpen className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate font-medium">{cat.name}</span>
            </button>
            {canManageStructure && (
              <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                <button
                  className="rounded p-1 hover:bg-background disabled:opacity-40"
                  onClick={(event) => {
                    event.stopPropagation();
                    void onMoveCategory(cat.id, "up", siblingCategoryIds);
                  }}
                  disabled={categoryIndex === 0}
                  title="Move folder up"
                >
                  <ArrowUp size={13} />
                </button>
                <button
                  className="rounded p-1 hover:bg-background disabled:opacity-40"
                  onClick={(event) => {
                    event.stopPropagation();
                    void onMoveCategory(cat.id, "down", siblingCategoryIds);
                  }}
                  disabled={categoryIndex === categories.length - 1}
                  title="Move folder down"
                >
                  <ArrowDown size={13} />
                </button>
                <button
                  className="rounded p-1 hover:bg-background"
                  onClick={() => onAddSubcategory(cat.id)}
                  title="Add subfolder"
                >
                  <FolderPlus size={13} />
                </button>
                <button
                  className="rounded p-1 hover:bg-background"
                  onClick={() => onEditCategory(cat.id)}
                  title="Edit folder"
                >
                  <Settings2 size={13} />
                </button>
              </div>
            )}
          </div>

          {!isCollapsed && (
            <>
              <div className="ml-4 space-y-0.5">
                {cat.pages.map((page, pageIndex) => (
                  <div
                    key={page.id}
                    className={`group/page flex items-center gap-1 rounded ${
                      selectedPageId === page.id ? "bg-primary text-primary-foreground" : ""
                    }`}
                  >
                    <button
                      onClick={() => onSelectPage(page.id)}
                      className={`min-w-0 flex-1 rounded px-2 py-1 text-left text-sm transition-colors ${
                        selectedPageId === page.id
                          ? "bg-primary text-primary-foreground"
                          : "hover:bg-accent"
                      }`}
                      draggable={canManageStructure}
                      onDragStart={(event) => onDragStartPage(page.id, cat.id, event)}
                      onDragEnd={onDragEnd}
                    >
                      <span className="truncate">{page.title}</span>
                    </button>
                    {canManageStructure && (
                      <div className="mr-1 flex items-center gap-0.5 opacity-0 transition-opacity group-hover/page:opacity-100">
                        <button
                          className="rounded p-1 hover:bg-background disabled:opacity-40"
                          onClick={(event) => {
                            event.stopPropagation();
                            void onMovePage(page.id, "up", cat.id, siblingPageIds);
                          }}
                          disabled={pageIndex === 0}
                          title="Move page up"
                        >
                          <ArrowUp size={12} />
                        </button>
                        <button
                          className="rounded p-1 hover:bg-background disabled:opacity-40"
                          onClick={(event) => {
                            event.stopPropagation();
                            void onMovePage(page.id, "down", cat.id, siblingPageIds);
                          }}
                          disabled={pageIndex === cat.pages.length - 1}
                          title="Move page down"
                        >
                          <ArrowDown size={12} />
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {cat.children.length > 0 && (
                <div className="ml-3">
                  <CategoryTree
                    categories={cat.children}
                    onSelectPage={onSelectPage}
                    selectedPageId={selectedPageId}
                    selectedCategoryId={selectedCategoryId}
                    onSelectCategory={onSelectCategory}
                    onAddSubcategory={onAddSubcategory}
                    onEditCategory={onEditCategory}
                    canManageStructure={canManageStructure}
                    activeDropTarget={activeDropTarget}
                    onDragStartCategory={onDragStartCategory}
                    onDragStartPage={onDragStartPage}
                    onDropOnCategory={onDropOnCategory}
                    onDragEnterCategory={onDragEnterCategory}
                    onDragLeaveCategory={onDragLeaveCategory}
                    onDragEnd={onDragEnd}
                    collapsedCategoryIds={collapsedCategoryIds}
                    onToggleCategoryCollapse={onToggleCategoryCollapse}
                    onMoveCategory={onMoveCategory}
                    onMovePage={onMovePage}
                  />
                </div>
              )}
            </>
          )}
        </div>
        );
      })}
    </div>
  );
}

export function WikiPage_() {
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { data: tree, isLoading } = useWikiTree();
  const { memberships, currentTenantId } = useAuthStore();
  const currentMembership = memberships.find((m) => m.tenant_id === currentTenantId);
  const canManageStructure =
    currentMembership?.role === "owner" || currentMembership?.role === "admin";
  const canRestoreRevisions = canManageStructure;

  const [selectedPageId, setSelectedPageId] = useState<string | null>(null);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [changeNote, setChangeNote] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [dragPayload, setDragPayload] = useState<DragPayload | null>(null);
  const [activeDropTarget, setActiveDropTarget] = useState<string | null>(null);
  const [dragError, setDragError] = useState("");
  const [appliedPageParam, setAppliedPageParam] = useState<string | null>(null);
  const [collapsedCategoryIds, setCollapsedCategoryIds] = useState<
    Record<string, boolean>
  >({});

  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
  const [folderName, setFolderName] = useState("");
  const [folderParentId, setFolderParentId] = useState("");
  const [folderSortOrder, setFolderSortOrder] = useState("0");
  const [folderError, setFolderError] = useState("");
  const [reindexStatus, setReindexStatus] = useState("");

  const { data: page } = useWikiPage(selectedPageId || "");
  const { data: revisions } = useWikiRevisions(selectedPageId || "");
  const { data: searchResults } = useWikiSearch(searchQuery);

  const createPage = useCreateWikiPage();
  const createCategory = useCreateWikiCategory();
  const updateCategory = useUpdateWikiCategory();
  const deleteCategory = useDeleteWikiCategory();
  const updatePage = useUpdateWikiPage();
  const deletePage = useDeleteWikiPage();
  const restoreRevision = useRestoreWikiRevision();
  const reindexWiki = useReindexWiki();

  const flatCategories = useMemo(
    () => flattenCategories(tree?.categories || []),
    [tree?.categories],
  );

  const editingCategory = useMemo(
    () =>
      editingCategoryId && tree
        ? findCategoryById(tree.categories, editingCategoryId)
        : null,
    [editingCategoryId, tree],
  );
  const requestedPageId = searchParams.get("pageId");

  useEffect(() => {
    if (!tree || !requestedPageId || appliedPageParam === requestedPageId) return;
    const pageCategoryId = findCategoryIdForPage(tree.categories, requestedPageId);
    const pageInUncategorized = tree.uncategorized_pages.some(
      (page) => page.id === requestedPageId,
    );
    if (!pageCategoryId && !pageInUncategorized) return;
    setSelectedPageId(requestedPageId);
    setSelectedCategoryId(pageCategoryId ?? null);
    setAppliedPageParam(requestedPageId);
  }, [tree, requestedPageId, appliedPageParam]);

  useEffect(() => {
    if (!tree || !selectedPageId) return;
    const pageCategoryId = findCategoryIdForPage(tree.categories, selectedPageId);
    setSelectedCategoryId(pageCategoryId ?? null);
  }, [tree, selectedPageId]);

  const handleEdit = () => {
    if (!page) return;
    setEditContent(page.markdown_content);
    setChangeNote("");
    setIsEditing(true);
  };

  const handleSave = () => {
    if (!page) return;
    updatePage.mutate({
      id: page.id,
      markdown_content: editContent,
      change_note: changeNote || undefined,
    });
    setIsEditing(false);
    setChangeNote("");
  };

  const handleCreatePage = () => {
    const title = prompt("Page title:");
    if (!title?.trim()) return;
    createPage.mutate({
      title: title.trim(),
      category_id: selectedCategoryId || undefined,
      markdown_content: `# ${title.trim()}\n\nContent goes here.`,
    });
  };

  const handleReindexWiki = async () => {
    if (!canManageStructure) return;
    setReindexStatus("");
    try {
      await reindexWiki.mutateAsync();
      setReindexStatus("Reindex queued. Chat results will improve after indexing finishes.");
    } catch (err: any) {
      setReindexStatus(err?.response?.data?.detail || "Failed to queue wiki reindex.");
    }
  };

  const handleCreateFolder = (parentId?: string | null) => {
    if (!canManageStructure) return;
    const name = prompt("Folder name:");
    if (!name?.trim()) return;
    createCategory.mutate({
      name: name.trim(),
      parent_id: parentId || undefined,
      sort_order: 0,
    });
  };

  const openFolderEditor = (categoryId: string) => {
    if (!canManageStructure || !tree) return;
    const category = findCategoryById(tree.categories, categoryId);
    if (!category) return;

    setEditingCategoryId(categoryId);
    setFolderName(category.name);
    setFolderParentId(category.parent_id || "");
    setFolderSortOrder(String(category.sort_order || 0));
    setFolderError("");
  };

  const closeFolderEditor = () => {
    setEditingCategoryId(null);
    setFolderName("");
    setFolderParentId("");
    setFolderSortOrder("0");
    setFolderError("");
  };

  const saveFolderEditor = async () => {
    if (!editingCategoryId) return;
    if (!folderName.trim()) {
      setFolderError("Folder name is required.");
      return;
    }

    try {
      await updateCategory.mutateAsync({
        id: editingCategoryId,
        name: folderName.trim(),
        parent_id: folderParentId || null,
        sort_order: Number.isFinite(Number(folderSortOrder))
          ? Number(folderSortOrder)
          : 0,
      });
      closeFolderEditor();
    } catch (err: any) {
      setFolderError(err?.response?.data?.detail || "Failed to update folder.");
    }
  };

  const removeFolder = async () => {
    if (!editingCategoryId) return;
    if (
      !confirm(
        "Delete this folder? Subfolders and pages will be moved to the parent folder.",
      )
    ) {
      return;
    }

    try {
      await deleteCategory.mutateAsync(editingCategoryId);
      if (selectedCategoryId === editingCategoryId) {
        setSelectedCategoryId(null);
      }
      closeFolderEditor();
    } catch (err: any) {
      setFolderError(err?.response?.data?.detail || "Failed to delete folder.");
    }
  };

  const toggleCategoryCollapse = (categoryId: string) => {
    setCollapsedCategoryIds((prev) => ({
      ...prev,
      [categoryId]: !prev[categoryId],
    }));
  };

  const moveCategoryWithinSiblings = async (
    categoryId: string,
    direction: "up" | "down",
    siblingCategoryIds: string[],
  ) => {
    if (!canManageStructure) return;
    const fromIndex = siblingCategoryIds.indexOf(categoryId);
    if (fromIndex === -1) return;
    const delta = direction === "up" ? -1 : 1;
    const toIndex = fromIndex + delta;
    if (toIndex < 0 || toIndex >= siblingCategoryIds.length) return;

    const reordered = [...siblingCategoryIds];
    [reordered[fromIndex], reordered[toIndex]] = [
      reordered[toIndex],
      reordered[fromIndex],
    ];

    try {
      await Promise.all(
        reordered.map((id, sortOrder) =>
          wikiApi.updateCategory(id, { sort_order: sortOrder }),
        ),
      );
      await queryClient.invalidateQueries({ queryKey: ["wiki-tree"] });
    } catch (err: any) {
      setDragError(err?.response?.data?.detail || "Unable to reorder folders.");
    }
  };

  const movePageWithinSiblings = async (
    pageId: string,
    direction: "up" | "down",
    categoryId: string | null,
    siblingPageIds: string[],
  ) => {
    if (!canManageStructure) return;
    const fromIndex = siblingPageIds.indexOf(pageId);
    if (fromIndex === -1) return;
    const delta = direction === "up" ? -1 : 1;
    const toIndex = fromIndex + delta;
    if (toIndex < 0 || toIndex >= siblingPageIds.length) return;

    const reordered = [...siblingPageIds];
    [reordered[fromIndex], reordered[toIndex]] = [
      reordered[toIndex],
      reordered[fromIndex],
    ];

    try {
      await Promise.all(
        reordered.map((id, sortOrder) =>
          wikiApi.updatePage(id, {
            category_id: categoryId,
            sort_order: sortOrder,
            change_note: "Reorder pages",
          }),
        ),
      );
      await queryClient.invalidateQueries({ queryKey: ["wiki-tree"] });
      if (selectedPageId) {
        await queryClient.invalidateQueries({ queryKey: ["wiki-page", selectedPageId] });
      }
    } catch (err: any) {
      setDragError(err?.response?.data?.detail || "Unable to reorder pages.");
    }
  };

  const handleDeletePage = async () => {
    if (!page || !canManageStructure) return;
    if (!confirm(`Delete page "${page.title}"? This cannot be undone.`)) {
      return;
    }
    await deletePage.mutateAsync(page.id);
    setSelectedPageId(null);
    setShowHistory(false);
  };

  const clearDragState = () => {
    setDragPayload(null);
    setActiveDropTarget(null);
  };

  const setDropTarget = (target: DropTarget) => {
    if (!dragPayload) return;
    setActiveDropTarget(dropTargetKey(target));
  };

  const clearDropTarget = (target: DropTarget) => {
    const key = dropTargetKey(target);
    setActiveDropTarget((current) => (current === key ? null : current));
  };

  const handleDragStartCategory = (
    categoryId: string,
    parentId: string | null,
    event: DragEvent<HTMLDivElement>,
  ) => {
    if (!canManageStructure) return;
    event.dataTransfer.effectAllowed = "move";
    setDragError("");
    setDragPayload({
      type: "category",
      id: categoryId,
      sourceParentId: parentId,
    });
  };

  const handleDragStartPage = (
    pageId: string,
    categoryId: string | null,
    event: DragEvent<HTMLButtonElement>,
  ) => {
    if (!canManageStructure) return;
    event.dataTransfer.effectAllowed = "move";
    setDragError("");
    setDragPayload({
      type: "page",
      id: pageId,
      sourceCategoryId: categoryId,
    });
  };

  const handleDropOnTarget = async (target: DropTarget) => {
    if (!dragPayload || !canManageStructure) return;
    setDragError("");

    try {
      if (dragPayload.type === "page") {
        const destinationCategoryId =
          target.type === "category" ? target.id : null;

        if (destinationCategoryId === dragPayload.sourceCategoryId) {
          clearDragState();
          return;
        }

        await updatePage.mutateAsync({
          id: dragPayload.id,
          category_id: destinationCategoryId,
          change_note: destinationCategoryId
            ? "Move page to folder"
            : "Move page to uncategorized",
        });

        if (selectedPageId === dragPayload.id) {
          setSelectedCategoryId(destinationCategoryId);
        }
      } else {
        const destinationParentId =
          target.type === "category" ? target.id : null;

        if (destinationParentId === dragPayload.id) {
          clearDragState();
          return;
        }
        if (destinationParentId === dragPayload.sourceParentId) {
          clearDragState();
          return;
        }

        await updateCategory.mutateAsync({
          id: dragPayload.id,
          parent_id: destinationParentId,
        });
      }
    } catch (err: any) {
      setDragError(err?.response?.data?.detail || "Unable to move item.");
    } finally {
      clearDragState();
    }
  };

  return (
    <div className="flex h-full">
      <div className="w-80 overflow-auto border-r border-border p-4">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-semibold">Wiki</h2>
          <div className="flex items-center gap-1">
            {canManageStructure && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => handleCreateFolder(selectedCategoryId)}
                title="New folder"
              >
                <FolderPlus size={16} />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={handleCreatePage}
              title="New page"
            >
              <Plus size={16} />
            </Button>
          </div>
        </div>

        {canManageStructure && selectedCategoryId && (
          <Button
            variant="outline"
            size="sm"
            className="mb-3 w-full"
            onClick={() => openFolderEditor(selectedCategoryId)}
          >
            <Settings2 size={14} /> Edit Selected Folder
          </Button>
        )}
        {canManageStructure && (
          <>
            <Button
              variant="outline"
              size="sm"
              className="mb-2 w-full"
              onClick={handleReindexWiki}
              disabled={reindexWiki.isPending}
            >
              <RefreshCw
                size={14}
                className={reindexWiki.isPending ? "animate-spin" : ""}
              />
              {reindexWiki.isPending ? "Reindexing..." : "Reindex Wiki"}
            </Button>
            {reindexStatus && (
              <p className="mb-3 text-xs text-muted-foreground">{reindexStatus}</p>
            )}
          </>
        )}
        {canManageStructure && (
          <p className="mb-2 text-xs text-muted-foreground">
            Drag pages into folders. Drag folders onto folders to restructure.
          </p>
        )}
        {canManageStructure && (
          <div
            className={`mb-3 rounded-md border border-dashed px-2 py-2 text-xs transition-colors ${
              activeDropTarget === "root"
                ? "border-primary bg-primary/10 text-primary"
                : "border-border text-muted-foreground"
            }`}
            onDragOver={(event) => {
              event.preventDefault();
              setDropTarget({ type: "root" });
            }}
            onDragLeave={() => clearDropTarget({ type: "root" })}
            onDrop={(event) => {
              event.preventDefault();
              void handleDropOnTarget({ type: "root" });
            }}
          >
            Drop here to move a folder to top level or a page to Uncategorized
          </div>
        )}
        {dragError && <p className="mb-3 text-xs text-destructive">{dragError}</p>}

        <div className="relative mb-4">
          <Search
            size={14}
            className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            placeholder="Search wiki..."
            className="h-8 pl-8 text-sm"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        {searchQuery && searchResults ? (
          <div className="space-y-1">
            <p className="mb-2 text-xs text-muted-foreground">
              {searchResults.length} results
            </p>
            {searchResults.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setSelectedPageId(p.id);
                  setSearchQuery("");
                }}
                className="w-full rounded px-2 py-1 text-left text-sm hover:bg-accent"
              >
                {p.title}
              </button>
            ))}
          </div>
        ) : isLoading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : tree ? (
          <>
            <CategoryTree
              categories={tree.categories}
              onSelectPage={setSelectedPageId}
              selectedPageId={selectedPageId}
              selectedCategoryId={selectedCategoryId}
              onSelectCategory={setSelectedCategoryId}
              onAddSubcategory={(parentId) => handleCreateFolder(parentId)}
              onEditCategory={openFolderEditor}
              canManageStructure={canManageStructure}
              activeDropTarget={activeDropTarget}
              onDragStartCategory={handleDragStartCategory}
              onDragStartPage={handleDragStartPage}
              onDropOnCategory={async (categoryId) => {
                await handleDropOnTarget({ type: "category", id: categoryId });
              }}
              onDragEnterCategory={(categoryId) =>
                setDropTarget({ type: "category", id: categoryId })
              }
              onDragLeaveCategory={(categoryId) =>
                clearDropTarget({ type: "category", id: categoryId })
              }
              onDragEnd={clearDragState}
              collapsedCategoryIds={collapsedCategoryIds}
              onToggleCategoryCollapse={toggleCategoryCollapse}
              onMoveCategory={moveCategoryWithinSiblings}
              onMovePage={movePageWithinSiblings}
            />
            {(tree.uncategorized_pages.length > 0 || canManageStructure) && (
              <div
                className={`mt-3 rounded-md p-1 ${
                  activeDropTarget === "uncategorized"
                    ? "border border-dashed border-primary/60 bg-primary/10"
                    : ""
                }`}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDropTarget({ type: "uncategorized" });
                }}
                onDragLeave={() => clearDropTarget({ type: "uncategorized" })}
                onDrop={(event) => {
                  event.preventDefault();
                  void handleDropOnTarget({ type: "uncategorized" });
                }}
              >
                <p className="px-2 py-1 text-xs font-medium text-muted-foreground">
                  Uncategorized
                </p>
                {tree.uncategorized_pages.map((p, pageIndex) => (
                  <div
                    key={p.id}
                    className={`group/page flex items-center gap-1 rounded ${
                      selectedPageId === p.id ? "bg-primary text-primary-foreground" : ""
                    }`}
                  >
                    <button
                      onClick={() => {
                        setSelectedPageId(p.id);
                        setSelectedCategoryId(null);
                      }}
                      className={`min-w-0 flex-1 rounded px-2 py-1 text-left text-sm transition-colors ${
                        selectedPageId === p.id
                          ? "bg-primary text-primary-foreground"
                          : "hover:bg-accent"
                      }`}
                      draggable={canManageStructure}
                      onDragStart={(event) => handleDragStartPage(p.id, null, event)}
                      onDragEnd={clearDragState}
                    >
                      <span className="truncate">{p.title}</span>
                    </button>
                    {canManageStructure && (
                      <div className="mr-1 flex items-center gap-0.5 opacity-0 transition-opacity group-hover/page:opacity-100">
                        <button
                          className="rounded p-1 hover:bg-background disabled:opacity-40"
                          onClick={(event) => {
                            event.stopPropagation();
                            void movePageWithinSiblings(
                              p.id,
                              "up",
                              null,
                              tree.uncategorized_pages.map((page) => page.id),
                            );
                          }}
                          disabled={pageIndex === 0}
                          title="Move page up"
                        >
                          <ArrowUp size={12} />
                        </button>
                        <button
                          className="rounded p-1 hover:bg-background disabled:opacity-40"
                          onClick={(event) => {
                            event.stopPropagation();
                            void movePageWithinSiblings(
                              p.id,
                              "down",
                              null,
                              tree.uncategorized_pages.map((page) => page.id),
                            );
                          }}
                          disabled={pageIndex === tree.uncategorized_pages.length - 1}
                          title="Move page down"
                        >
                          <ArrowDown size={12} />
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        ) : null}
      </div>

      <div className="flex-1 overflow-auto p-8">
        {page ? (
          <div>
            <div className="mb-4 flex items-center justify-between">
              <h1 className="text-2xl font-bold">{page.title}</h1>
              <div className="flex gap-2">
                {canManageStructure && (
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleDeletePage}
                    disabled={deletePage.isPending}
                  >
                    <Trash2 size={14} /> Delete
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowHistory((v) => !v)}
                >
                  <History size={16} /> History
                </Button>
                {isEditing ? (
                  <Button size="sm" onClick={handleSave}>
                    <Save size={16} /> Save
                  </Button>
                ) : (
                  <Button variant="outline" size="sm" onClick={handleEdit}>
                    Edit
                  </Button>
                )}
              </div>
            </div>

            {showHistory && (
              <Card className="mb-4 p-4">
                <h3 className="mb-3 text-sm font-semibold">Revision History</h3>
                {revisions && revisions.length > 0 ? (
                  <div className="space-y-2">
                    {revisions.map((revision) => (
                      <div
                        key={revision.id}
                        className="flex items-center justify-between rounded-md border border-border px-3 py-2"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">
                            v{revision.version} · {revision.title}
                          </p>
                          <p className="truncate text-xs text-muted-foreground">
                            {new Date(revision.created_at).toLocaleString()}
                            {revision.change_note ? ` · ${revision.change_note}` : ""}
                          </p>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={restoreRevision.isPending || !canRestoreRevisions}
                          onClick={() => {
                            if (page && confirm("Restore this revision?")) {
                              restoreRevision.mutate({
                                pageId: page.id,
                                revisionId: revision.id,
                              });
                            }
                          }}
                        >
                          Restore
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No revisions yet.</p>
                )}
                {!canRestoreRevisions && (
                  <p className="mt-3 text-xs text-muted-foreground">
                    Only tenant admins can restore revisions.
                  </p>
                )}
              </Card>
            )}

            {isEditing ? (
              <div>
                <Input
                  className="mb-3"
                  placeholder="Revision note (optional)"
                  value={changeNote}
                  onChange={(e) => setChangeNote(e.target.value)}
                />
                <textarea
                  className="h-[calc(100vh-300px)] w-full resize-none rounded-md border border-border p-4 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                />
              </div>
            ) : (
              <div className="prose prose-sm max-w-none">
                <ReactMarkdown>{page.markdown_content}</ReactMarkdown>
              </div>
            )}
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground">
            <div className="text-center">
              <BookOpen size={48} className="mx-auto mb-3 opacity-50" />
              <p>Select a page from the sidebar</p>
            </div>
          </div>
        )}
      </div>

      {editingCategoryId && editingCategory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <Card className="w-full max-w-lg p-6">
            <h3 className="mb-4 text-lg font-semibold">Edit Folder</h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium">Folder Name</label>
                <Input
                  className="mt-1"
                  value={folderName}
                  onChange={(e) => setFolderName(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium">Parent Folder</label>
                <select
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  value={folderParentId}
                  onChange={(e) => setFolderParentId(e.target.value)}
                >
                  <option value="">Top level</option>
                  {flatCategories
                    .filter((category) => category.id !== editingCategoryId)
                    .map((category) => (
                      <option key={category.id} value={category.id}>
                        {`${"  ".repeat(category.depth)}${category.name}`}
                      </option>
                    ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">Sort Order</label>
                <Input
                  className="mt-1"
                  type="number"
                  value={folderSortOrder}
                  onChange={(e) => setFolderSortOrder(e.target.value)}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Deleting this folder moves its pages and subfolders to the parent folder.
              </p>
              {folderError && <p className="text-sm text-destructive">{folderError}</p>}
            </div>
            <div className="mt-5 flex items-center justify-between">
              <Button
                variant="destructive"
                disabled={deleteCategory.isPending}
                onClick={removeFolder}
              >
                <Trash2 size={14} /> Delete Folder
              </Button>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  onClick={closeFolderEditor}
                  disabled={updateCategory.isPending || deleteCategory.isPending}
                >
                  Cancel
                </Button>
                <Button
                  onClick={saveFolderEditor}
                  disabled={updateCategory.isPending || deleteCategory.isPending}
                >
                  Save Folder
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
