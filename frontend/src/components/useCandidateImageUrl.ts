import { useEffect, useState } from "react";
import { authorizedBlob } from "../api/client";

export function useCandidateImageUrl(blogClipId: number | null, imageId: number | null) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (blogClipId == null || imageId == null) {
      setUrl(null);
      setError(false);
      return;
    }

    let cancelled = false;
    let objectUrl: string | null = null;
    setUrl(null);
    setError(false);

    authorizedBlob(`/blog-clips/${blogClipId}/images/${imageId}/file`)
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
  }, [blogClipId, imageId]);

  return { url, error };
}
