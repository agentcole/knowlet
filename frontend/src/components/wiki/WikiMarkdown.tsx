import { useEffect, useId, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function isProtectedAssetUrl(value: string | undefined): boolean {
  if (!value) return false;
  return /\/api\/v1\/wiki\/assets\/[^/]+\/content$/.test(value);
}

async function fetchAssetBlob(assetUrl: string, signal?: AbortSignal): Promise<Blob> {
  const token = localStorage.getItem("access_token");
  const tenantId = localStorage.getItem("tenant_id");
  const response = await fetch(assetUrl, {
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "X-Tenant-ID": tenantId || "",
    },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Failed to load asset (${response.status})`);
  }
  return await response.blob();
}

function ProtectedAssetImage({
  src,
  alt,
}: {
  src: string;
  alt?: string;
}) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let objectUrl = "";
    setBlobUrl(null);
    setError(false);

    void fetchAssetBlob(src, controller.signal)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setError(true);
        }
      });

    return () => {
      controller.abort();
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [src]);

  if (error) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        Failed to load image.
      </div>
    );
  }

  if (!blobUrl) {
    return (
      <div className="rounded-md border border-border bg-muted/40 px-3 py-6 text-center text-sm text-muted-foreground">
        Loading image...
      </div>
    );
  }

  return (
    <img
      alt={alt || ""}
      className="my-4 max-h-[520px] w-full rounded-md border border-border object-contain"
      src={blobUrl}
    />
  );
}

function ProtectedAssetLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  const [downloading, setDownloading] = useState(false);

  const handleClick = async (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    if (downloading) return;
    setDownloading(true);
    try {
      const blob = await fetchAssetBlob(href);
      const objectUrl = URL.createObjectURL(blob);
      window.open(objectUrl, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <a className="text-primary underline-offset-4 hover:underline" href={href} onClick={handleClick}>
      {downloading ? "Opening..." : children}
    </a>
  );
}

function MermaidBlock({ code }: { code: string }) {
  const [svg, setSvg] = useState("");
  const [error, setError] = useState("");
  const renderId = useId().replace(/[:]/g, "");

  useEffect(() => {
    let active = true;
    setSvg("");
    setError("");

    void import("mermaid")
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({
          startOnLoad: false,
          theme: "neutral",
          securityLevel: "strict",
        });
        const result = await mermaid.render(`mermaid-${renderId}`, code);
        if (active) {
          setSvg(result.svg);
        }
      })
      .catch(() => {
        if (active) {
          setError("Failed to render Mermaid diagram.");
        }
      });

    return () => {
      active = false;
    };
  }, [code, renderId]);

  if (error) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        {error}
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="rounded-md border border-border bg-muted/40 px-3 py-6 text-center text-sm text-muted-foreground">
        Rendering diagram...
      </div>
    );
  }

  return (
    <div
      className="my-4 overflow-x-auto rounded-md border border-border bg-white p-4"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

export function WikiMarkdown({ content }: { content: string }) {
  return (
    <div className="prose prose-sm max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ inline, className, children, ...props }: any) {
            const code = String(children || "").replace(/\n$/, "");
            if (!inline && className === "language-mermaid") {
              return <MermaidBlock code={code} />;
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            );
          },
          img({ src, alt }: any) {
            if (typeof src === "string" && isProtectedAssetUrl(src)) {
              return <ProtectedAssetImage alt={alt} src={src} />;
            }
            return (
              <img
                alt={alt || ""}
                className="my-4 max-h-[520px] w-full rounded-md border border-border object-contain"
                src={src}
              />
            );
          },
          a({ href, children, ...props }: any) {
            if (typeof href === "string" && isProtectedAssetUrl(href)) {
              return <ProtectedAssetLink href={href}>{children}</ProtectedAssetLink>;
            }
            return (
              <a
                href={href}
                rel="noreferrer"
                target="_blank"
                {...props}
              >
                {children}
              </a>
            );
          },
          table({ children }: any) {
            return (
              <div className="my-4 overflow-x-auto">
                <table className="w-full border-collapse text-sm">{children}</table>
              </div>
            );
          },
          th({ children }: any) {
            return <th className="border border-border bg-muted/40 px-3 py-2 text-left">{children}</th>;
          },
          td({ children }: any) {
            return <td className="border border-border px-3 py-2 align-top">{children}</td>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
