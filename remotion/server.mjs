/**
 * Remotion render sidecar for New Cut blog shorts (R3).
 *
 * POST /render  { compositionId?, props, outputPath }
 * GET  /health
 *
 * Run: npm run service  (default http://127.0.0.1:3100)
 *
 * Note: `bundle()` snapshots `public/` once. Backend materializes board images /
 * narration into remotion/public/clips/{id}/ *after* that, so we sync those
 * files into the bundle's public/ before every render.
 */

import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import express from "express";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_PUBLIC = path.join(__dirname, "public");
const PORT = Number(process.env.REMOTION_SERVICE_PORT || 3100);
const HOST = process.env.REMOTION_SERVICE_HOST || "127.0.0.1";
const TOKEN = (process.env.REMOTION_SERVICE_TOKEN || "").trim();

const app = express();
app.use(express.json({ limit: "20mb" }));

let bundlePromise = null;

function getServeUrl() {
  if (!bundlePromise) {
    const entryPoint = path.join(__dirname, "src", "index.ts");
    console.log(`[remotion-service] bundling ${entryPoint}…`);
    bundlePromise = bundle({
      entryPoint,
      publicDir: PROJECT_PUBLIC,
      webpackOverride: (config) => config,
    }).then((serveUrl) => {
      console.log(`[remotion-service] bundle ready: ${serveUrl}`);
      return serveUrl;
    });
  }
  return bundlePromise;
}

/**
 * Copy live remotion/public assets into the webpack bundle public folder.
 * Required because board images / narration are written after the first bundle().
 */
function syncProjectPublicIntoBundle(serveUrl) {
  const destPublic = path.join(serveUrl, "public");
  fs.mkdirSync(destPublic, { recursive: true });

  const srcClips = path.join(PROJECT_PUBLIC, "clips");
  if (!fs.existsSync(srcClips)) {
    console.warn(`[remotion-service] no project public/clips yet at ${srcClips}`);
    return;
  }

  const destClips = path.join(destPublic, "clips");
  fs.cpSync(srcClips, destClips, { recursive: true });
  console.log(`[remotion-service] synced public/clips → ${destClips}`);
}

function assertAuth(req, res) {
  if (!TOKEN) return true;
  const header = req.headers.authorization || "";
  const expected = `Bearer ${TOKEN}`;
  if (header !== expected) {
    res.status(401).json({ detail: "Unauthorized" });
    return false;
  }
  return true;
}

app.get("/health", async (_req, res) => {
  try {
    await getServeUrl();
    res.json({ ok: true, service: "new-cut-remotion", port: PORT });
  } catch (err) {
    res.status(500).json({ ok: false, detail: String(err) });
  }
});

app.post("/render", async (req, res) => {
  if (!assertAuth(req, res)) return;

  const compositionId = req.body?.compositionId || "BlogShorts";
  const props = req.body?.props;
  const outputPath = req.body?.outputPath;

  if (!props || typeof props !== "object") {
    res.status(400).json({ detail: "props object is required" });
    return;
  }
  if (!outputPath || typeof outputPath !== "string") {
    res.status(400).json({ detail: "outputPath string is required" });
    return;
  }

  const resolvedOut = path.resolve(outputPath);
  fs.mkdirSync(path.dirname(resolvedOut), { recursive: true });

  const started = Date.now();
  const clipId = props?.blogClipId ?? "?";
  try {
    const serveUrl = await getServeUrl();
    syncProjectPublicIntoBundle(serveUrl);

    const composition = await selectComposition({
      serveUrl,
      id: compositionId,
      inputProps: props,
    });

    console.log(
      `[remotion-service] render start clip=${clipId} ${compositionId} → ${resolvedOut} (${composition.durationInFrames} frames)`,
    );

    await renderMedia({
      composition,
      serveUrl,
      codec: "h264",
      // Sharper stills from blog photos (default CRF is softer).
      crf: 16,
      jpegQuality: 92,
      outputLocation: resolvedOut,
      inputProps: props,
      overwrite: true,
    });

    const stat = fs.statSync(resolvedOut);
    const elapsedMs = Date.now() - started;
    console.log(
      `[remotion-service] render ok clip=${clipId} bytes=${stat.size} elapsedMs=${elapsedMs}`,
    );
    res.json({
      ok: true,
      outputPath: resolvedOut,
      bytes: stat.size,
      durationInFrames: composition.durationInFrames,
      fps: composition.fps,
      width: composition.width,
      height: composition.height,
      elapsedMs,
    });
  } catch (err) {
    const elapsedMs = Date.now() - started;
    console.error(
      `[remotion-service] render failed clip=${clipId} elapsedMs=${elapsedMs}`,
      err,
    );
    res.status(500).json({
      detail: err instanceof Error ? err.message : String(err),
      elapsedMs,
    });
  }
});

app.listen(PORT, HOST, () => {
  console.log(`[remotion-service] listening on http://${HOST}:${PORT}`);
  void getServeUrl().catch((err) => {
    console.error("[remotion-service] initial bundle failed", err);
  });
});
