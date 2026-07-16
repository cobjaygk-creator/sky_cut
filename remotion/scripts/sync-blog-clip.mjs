/**
 * Fetch GET /blog-clips/{id}/remotion-props (materialize=true) and write props JSON.
 *
 * Env:
 *   NEW_CUT_API_BASE   default http://127.0.0.1:8000
 *   NEW_CUT_API_TOKEN  Bearer token (or use email/password below)
 *   NEW_CUT_EMAIL / NEW_CUT_PASSWORD  optional login
 *
 * Usage:
 *   node scripts/sync-blog-clip.mjs 3
 */

import { writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const remotionRoot = path.resolve(__dirname, "..");

async function login(base, email, password) {
  const res = await fetch(`${base}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    throw new Error(`Login failed: ${res.status} ${await res.text()}`);
  }
  const data = await res.json();
  return data.access_token;
}

async function main() {
  const clipId = Number(process.argv[2]);
  if (!Number.isFinite(clipId) || clipId < 1) {
    console.error("Usage: node scripts/sync-blog-clip.mjs <blog_clip_id>");
    process.exit(1);
  }

  const base = (process.env.NEW_CUT_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
  let token = process.env.NEW_CUT_API_TOKEN || "";
  if (!token) {
    const email = process.env.NEW_CUT_EMAIL;
    const password = process.env.NEW_CUT_PASSWORD;
    if (!email || !password) {
      console.error("Set NEW_CUT_API_TOKEN or NEW_CUT_EMAIL + NEW_CUT_PASSWORD");
      process.exit(1);
    }
    token = await login(base, email, password);
  }

  const url = `${base}/blog-clips/${clipId}/remotion-props?materialize=true`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`remotion-props failed: ${res.status} ${await res.text()}`);
  }
  const props = await res.json();

  const outDir = path.join(remotionRoot, "out");
  await mkdir(outDir, { recursive: true });
  const outPath = path.join(outDir, `props-${clipId}.json`);
  await writeFile(outPath, JSON.stringify(props, null, 2), "utf8");

  console.log(`Wrote ${outPath}`);
  console.log(`Boards: ${props.boards?.length ?? 0}`);
  console.log(`Render: npx remotion render BlogShorts out/blog-clip-${clipId}.mp4 --props=${outPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
