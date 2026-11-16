// Captures d'écran (frontend/e2e-captures/captures.spec.ts) : chaque capture citée par une page
// existe et a un texte alternatif ; chaque capture du scénario est utilisée par une page.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const SITE = fileURLToPath(new URL("..", import.meta.url));
const DOCS = join(SITE, "src/content/docs");
const CAPTURES = join(SITE, "src/assets/captures/fr");
const BALISE = /<Capture\b([^>]*?)\/>/g;
const attribut = (attributs, nom) => new RegExp(`\\b${nom}="([^"]*)"`).exec(attributs)?.[1];

export function usages(source) {
  return [...source.matchAll(BALISE)].map(([, a]) => ({ nom: attribut(a, "nom"), alt: attribut(a, "alt") }));
}

const pages = readdirSync(DOCS, { recursive: true })
  .filter((p) => p.endsWith(".mdx"))
  .map((p) => join(DOCS, p));
const cites = pages.flatMap((p) => usages(readFileSync(p, "utf8")).map((u) => ({ ...u, page: p })));

test("usages lit nom et alt, dans n'importe quel ordre et sur plusieurs lignes", () => {
  assert.deepEqual(usages(`<Capture nom="a-b" alt="Texte" />`), [{ nom: "a-b", alt: "Texte" }]);
  assert.deepEqual(usages(`x\n<Capture\n  alt="L'écran"\n  nom="c"\n/>`), [{ nom: "c", alt: "L'écran" }]);
  assert.deepEqual(usages("aucune"), []);
});

test("chaque capture citée existe et a un texte alternatif (IHM-07)", () => {
  const problemes = cites.flatMap(({ nom, alt, page }) => [
    ...(existsSync(join(CAPTURES, `${nom}.png`)) ? [] : [`${page} : ${nom}.png absente`]),
    ...(alt?.trim() ? [] : [`${page} : ${nom} sans alt`]),
  ]);
  assert.deepEqual(problemes, []);
});

test("chaque capture du scénario est prise et citée par une page", () => {
  const scenario = readFileSync(join(SITE, "../frontend/e2e-captures/captures.spec.ts"), "utf8");
  const noms = [...scenario.matchAll(/nom: '([a-z0-9-]+)'/g)].map(([, n]) => n);
  assert.ok(noms.length > 0);
  const citees = new Set(cites.map((c) => c.nom));
  assert.deepEqual(noms.filter((n) => !citees.has(n) || !existsSync(join(CAPTURES, `${n}.png`))), []);
  assert.deepEqual(readdirSync(CAPTURES).map((f) => f.replace(/\.png$/, "")).sort(), [...noms].sort());
});
