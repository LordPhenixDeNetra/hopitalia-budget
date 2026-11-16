// En-têtes de sécurité de la documentation (location /docs/ de frontend/nginx.conf), écrits après la
// construction dans en-tetes-docs.conf. Starlight insère des scripts inline (thème, menu) : la
// politique autorise chacun par son empreinte, jamais par 'unsafe-inline'. La recherche (Pagefind)
// charge un module WebAssembly : 'wasm-unsafe-eval'. Le reste suit la politique de l'interface.
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const INLINE = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g;

export function empreintes(html) {
  return [...html.matchAll(INLINE)].map(([, corps]) => `'sha256-${createHash("sha256").update(corps).digest("base64")}'`);
}

export function politique(hashes) {
  return [
    "default-src 'self'",
    `script-src 'self' 'wasm-unsafe-eval' ${[...hashes].sort().join(" ")}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join("; ");
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const dist = fileURLToPath(new URL("../dist/", import.meta.url));
  const hashes = new Set(
    readdirSync(dist, { recursive: true })
      .filter((f) => f.endsWith(".html"))
      .flatMap((f) => empreintes(readFileSync(join(dist, f), "utf8"))),
  );
  // Un add_header dans une location remplace ceux du serveur : tous les en-têtes sont repris ici.
  const entetes = [
    `add_header Content-Security-Policy "${politique(hashes)}" always;`,
    `add_header X-Content-Type-Options "nosniff" always;`,
    `add_header X-Frame-Options "DENY" always;`,
    `add_header Referrer-Policy "same-origin" always;`,
    `add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;`,
  ];
  writeFileSync(new URL("../en-tetes-docs.conf", import.meta.url), `${entetes.join("\n")}\n`);
  console.log(`en-tetes-docs.conf : ${hashes.size} script(s) inline autorisé(s) par empreinte`);
}
