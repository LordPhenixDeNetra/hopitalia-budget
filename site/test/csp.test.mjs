// Empreintes des scripts inline et politique de sécurité de la documentation (scripts/csp.mjs).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { empreintes, politique } from "../scripts/csp.mjs";

const sha = (texte) => `'sha256-${createHash("sha256").update(texte).digest("base64")}'`;

test("empreintes prend chaque script inline, pas les scripts chargés par src", () => {
  const html = `<script>a()</script><script type="module" src="/x.js"></script><script is="x">\nb()\n</script>`;
  assert.deepEqual(empreintes(html), [sha("a()"), sha("\nb()\n")]);
});

test("la politique n'autorise aucun script inline sans empreinte", () => {
  const p = politique(new Set([sha("a()")]));
  assert.match(p, /script-src 'self' 'wasm-unsafe-eval' 'sha256-/);
  assert.doesNotMatch(p.split("; ").find((d) => d.startsWith("script-src")), /unsafe-inline/);
  assert.match(p, /frame-ancestors 'none'/);
});
