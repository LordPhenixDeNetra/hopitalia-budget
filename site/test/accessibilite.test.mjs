// axe (WCAG 2.1 A et AA) sur des pages construites (après `npm run build`), une de chaque modèle :
// accueil, page de concepts, page d'écran avec capture, référence, page anglaise. jsdom ne calcule
// pas la mise en page : les contrastes relèvent du thème de Starlight, pas de ce test.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { JSDOM } from "jsdom";

const axe = readFileSync(createRequire(import.meta.url).resolve("axe-core/axe.min.js"), "utf8");

async function defauts(chemin) {
  const html = readFileSync(new URL(`../dist/${chemin}`, import.meta.url), "utf8");
  const dom = new JSDOM(html, { runScripts: "outside-only", url: "http://localhost/docs/" });
  dom.window.eval(axe);
  const resultat = await dom.window.axe.run(dom.window.document, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
    rules: { "color-contrast": { enabled: false } },
  });
  return resultat.violations.map((v) => `${v.id} : ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

for (const page of [
  "index.html",
  "en/index.html",
  "decouvrir/concepts/index.html",
  "decouvrir/profils/index.html",
  "utiliser/engagements/index.html",
  "utiliser/alertes/index.html",
  "administrer/circuits/index.html",
  "installer/sauvegarde/index.html",
  "integrer/erreurs/index.html",
  "404.html",
]) {
  test(`${page} : aucun défaut d'accessibilité (IHM-07)`, async () => {
    const trouves = await defauts(page);
    assert.equal(trouves.length, 0, trouves.join("\n"));
  });
}
