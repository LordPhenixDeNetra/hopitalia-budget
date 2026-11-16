// Site de documentation de Hopitalia Budget, servi par l'interface sous /docs/ (frontend/nginx.conf).
// Français à la racine, anglais sous /en/ : une page pas encore traduite s'affiche en français, avec
// l'avis de Starlight.
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import starlightLinksValidator from "starlight-links-validator";

// Un groupe du menu par partie ; ses pages viennent de son dossier.
const partie = (label, en, directory) => ({ label, translations: { en }, items: [{ autogenerate: { directory } }] });

export default defineConfig({
  base: "/docs",
  trailingSlash: "always",
  integrations: [
    starlight({
      title: "Hopitalia Budget",
      favicon: "/favicon.svg",
      logo: { src: "./src/assets/logo.svg" },
      defaultLocale: "root",
      locales: {
        root: { label: "Français", lang: "fr" },
        en: { label: "English", lang: "en" },
      },
      customCss: ["./src/styles/theme.css"],
      // Un lien vers une page anglaise pas encore traduite est permis : Starlight sert la page française.
      plugins: [starlightLinksValidator({ errorOnFallbackPages: false })],
      sidebar: [
        partie("Découvrir", "Discover", "decouvrir"),
        partie("Installer et exploiter", "Install and operate", "installer"),
        partie("Utiliser", "Use", "utiliser"),
        partie("Administrer", "Administer", "administrer"),
        partie("Intégrer", "Integrate", "integrer"),
        partie("Notes de version", "Release notes", "versions"),
      ],
    }),
  ],
});
