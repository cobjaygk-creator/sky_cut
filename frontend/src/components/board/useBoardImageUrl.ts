import { useEffect, useState } from "react";
import { authorizedBlob } from "../../api/client";

export function useBoardImageUrl(blogClipId: number | null, boardId: number | null, cacheKey?: string) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (blogClipId == null || boardId == null) {
      setUrl(null);
      setError(false);
      return;
    }

    let cancelled = false;
    let objectUrl: string | null = null;
    setUrl(null);
    setError(false);

    authorizedBlob(`/blog-clips/${blogClipId}/boards/${boardId}/image`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [blogClipId, boardId, cacheKey]);

  return { url, error };
}
