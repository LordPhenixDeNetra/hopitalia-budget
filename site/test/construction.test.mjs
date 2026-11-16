// Le site construit (après `npm run build`) : les deux langues, l'accueil de chaque partie, la page
// 404, l'index de recherche, et les en-têtes de sécurité qui couvrent chaque script inline.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { empreintes } from "../scripts/csp.mjs";

const dist = new URL("../dist/", import.meta.url);
const lire = (p) => readFileSync(new URL(p, dist), "utf8");
const PARTIES = ["decouvrir", "installer", "utiliser", "administrer", "integrer", "versions"];

test("l'accueil est en français à la racine, en anglais sous en/", () => {
  assert.match(lire("index.html"), /<html[^>]*lang="fr"/);
  assert.match(lire("en/index.html"), /<html[^>]*lang="en"/);
});

test("chaque partie a sa page d'accueil", () => {
  for (const partie of PARTIES) assert.ok(existsSync(new URL(`${partie}/index.html`, dist)), partie);
});

test("une page pas encore traduite s'affiche en français à l'adresse anglaise, avec l'avis", () => {
  assert.match(lire("en/utiliser/alertes/index.html"), /This content is not available in your language yet/);
});

test("le site a une page 404 et un index de recherche hors ligne", () => {
  assert.ok(existsSync(new URL("404.html", dist)));
  assert.ok(existsSync(new URL("pagefind/", dist)));
});

test("une capture est servie en WebP sous /docs/", () => {
  const src = /<figure class="capture[^"]*"[^>]*>\s*<img[^>]*src="([^"]+)"/.exec(lire("utiliser/alertes/index.html"))?.[1];
  assert.match(src ?? "", /^\/docs\/_astro\/.+\.webp$/);
});

test("les en-têtes de la documentation autorisent chaque script inline par son empreinte", () => {
  const entetes = readFileSync(new URL("../en-tetes-docs.conf", import.meta.url), "utf8");
  assert.doesNotMatch(entetes, /'unsafe-inline'[^;]*script|script-src[^;]*'unsafe-inline'/);
  const pages = readdirSync(dist, { recursive: true }).filter((f) => f.endsWith(".html"));
  const manquantes = pages.flatMap((p) => empreintes(lire(p)).filter((h) => !entetes.includes(h)).map((h) => `${p} ${h}`));
  assert.deepEqual(manquantes, []);
  for (const entete of ["X-Frame-Options", "X-Content-Type-Options", "Referrer-Policy", "Permissions-Policy"]) {
    assert.match(entetes, new RegExp(`add_header ${entete} `), entete);
  }
});
