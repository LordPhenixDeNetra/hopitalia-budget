"""Rendu des états (ENF-09) en CSV, tableur (XLSX) et PDF, sans dépendance externe.

Le PDF est en Courier (chasse fixe : colonnes et montants alignés sans table de largeurs) et en
WinAnsiEncoding, qui couvre le français. Le tableur est un classeur XLSX minimal : une feuille,
montants en nombres exacts (chaîne décimale, jamais de flottant).
"""

import csv
import io
import zipfile
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal
from xml.sax.saxutils import escape

TypeColonne = Literal["texte", "montant", "nombre", "date"]
Valeur = str | int | Decimal | date | None


@dataclass(frozen=True)
class Colonne:
    cle: str
    libelle: str
    type: TypeColonne = "texte"


@dataclass(frozen=True)
class Etat:
    code: str
    titre: str
    sous_titre: str
    colonnes: list[Colonne]
    lignes: list[dict[str, Valeur]]
    totaux: dict[str, Valeur] = field(default_factory=dict)
    libelle_total: str = "Total"


def formater(valeur: Valeur, type_colonne: TypeColonne, langue: str) -> str:
    """Valeur lisible pour le PDF : séparateur de milliers et dates selon la langue (I18N-05)."""
    if valeur is None:
        return ""
    if type_colonne == "montant" and isinstance(valeur, Decimal):
        texte = f"{valeur:,.2f}"
        return texte.replace(",", " ").replace(".", ",") if langue == "fr" else texte
    if type_colonne == "date" and isinstance(valeur, date):
        return valeur.strftime("%d/%m/%Y") if langue == "fr" else valeur.isoformat()
    return str(valeur)


def _brut(valeur: Valeur) -> str:
    if valeur is None:
        return ""
    if isinstance(valeur, Decimal):
        return format(valeur, "f")
    if isinstance(valeur, date):
        return valeur.isoformat()
    return str(valeur)


def _lignes_avec_total(etat: Etat) -> list[dict[str, Valeur]]:
    if not etat.totaux:
        return etat.lignes
    premiere = etat.colonnes[0].cle
    return [*etat.lignes, {premiere: etat.libelle_total, **etat.totaux}]


def vers_csv(etat: Etat) -> bytes:
    """CSV pour tableur : séparateur « ; », BOM UTF-8, valeurs brutes (montants exacts)."""
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow([c.libelle for c in etat.colonnes])
    for ligne in _lignes_avec_total(etat):
        ecrivain.writerow([_brut(ligne.get(c.cle)) for c in etat.colonnes])
    return ("﻿" + sortie.getvalue()).encode("utf-8")


# Espaces de noms Office Open XML.
PAQUET = "http://schemas.openxmlformats.org/package/2006"
RELS_MIME = "application/vnd.openxmlformats-package.relationships+xml"
OOXML = "application/vnd.openxmlformats-officedocument"
TABLEUR = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELATIONS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _colonne_excel(index: int) -> str:
    lettres = ""
    index += 1
    while index:
        index, reste = divmod(index - 1, 26)
        lettres = chr(65 + reste) + lettres
    return lettres


def vers_xlsx(etat: Etat) -> bytes:
    """Classeur XLSX d'une feuille : en-tête, lignes, total ; montants et nombres numériques."""

    def cellule(ref: str, valeur: Valeur, numerique: bool) -> str:
        if valeur is None or valeur == "":
            return ""
        if numerique and isinstance(valeur, Decimal | int):
            return f'<c r="{ref}"><v>{_brut(valeur)}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t>{escape(_brut(valeur))}</t></is></c>'

    rangees = []
    lignes: list[dict[str, Valeur]] = [
        {c.cle: c.libelle for c in etat.colonnes},
        *_lignes_avec_total(etat),
    ]
    for numero, ligne in enumerate(lignes, start=1):
        cellules = "".join(
            cellule(
                f"{_colonne_excel(i)}{numero}",
                ligne.get(c.cle),
                numero > 1 and c.type in ("montant", "nombre"),
            )
            for i, c in enumerate(etat.colonnes)
        )
        rangees.append(f'<row r="{numero}">{cellules}</row>')
    nom_feuille = escape("".join(ch for ch in etat.titre if ch not in "[]:*?/\\")[:31])
    entete_xml = '<?xml version="1.0" encoding="UTF-8"?>'
    feuille = f"{OOXML}.spreadsheetml.sheet.main+xml"
    fichiers = {
        "[Content_Types].xml": (
            f'{entete_xml}<Types xmlns="{PAQUET}/content-types">'
            f'<Default Extension="rels" ContentType="{RELS_MIME}"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/xl/workbook.xml" ContentType="{feuille}"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            f'ContentType="{OOXML}.spreadsheetml.worksheet+xml"/></Types>'
        ),
        "_rels/.rels": (
            f'{entete_xml}<Relationships xmlns="{PAQUET}/relationships">'
            f'<Relationship Id="rId1" Type="{RELATIONS}/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            f'{entete_xml}<workbook xmlns="{TABLEUR}" xmlns:r="{RELATIONS}">'
            f'<sheets><sheet name="{nom_feuille}" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            f'{entete_xml}<Relationships xmlns="{PAQUET}/relationships">'
            f'<Relationship Id="rId1" Type="{RELATIONS}/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>'
        ),
        "xl/worksheets/sheet1.xml": (
            f'{entete_xml}<worksheet xmlns="{TABLEUR}">'
            f"<sheetData>{''.join(rangees)}</sheetData></worksheet>"
        ),
    }
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        for nom, contenu in fichiers.items():
            archive.writestr(nom, contenu)
    return tampon.getvalue()


# --- PDF -----------------------------------------------------------------------------------------

LARGEUR, HAUTEUR, MARGE = 842, 595, 30  # A4 paysage, en points
TAILLE, INTERLIGNE = 8, 11
CARACTERES = int((LARGEUR - 2 * MARGE) / (TAILLE * 0.6))  # Courier : 0,6 em par caractère
LIGNES_PAR_PAGE = int((HAUTEUR - 2 * MARGE) / INTERLIGNE) - 4


def _texte_pdf(texte: str) -> bytes:
    brut = texte.encode("cp1252", errors="replace")
    return brut.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _ajuster(texte: str, largeur: int, droite: bool) -> str:
    if len(texte) > largeur:
        texte = texte[: max(largeur - 1, 0)] + "…"
    return texte.rjust(largeur) if droite else texte.ljust(largeur)


def vers_pdf(etat: Etat, langue: str) -> bytes:
    """Tableau paginé : titre, filtres, en-tête répété, total, numéros de page."""
    lignes = [
        [formater(ligne.get(c.cle), c.type, langue) for c in etat.colonnes]
        for ligne in _lignes_avec_total(etat)
    ]
    largeurs = [
        max([len(c.libelle), *(len(lg[i]) for lg in lignes)]) for i, c in enumerate(etat.colonnes)
    ]
    disponible = CARACTERES - 2 * (len(largeurs) - 1)
    while sum(largeurs) > disponible:  # on rogne d'abord la colonne la plus large
        plus_large = largeurs.index(max(largeurs))
        largeurs[plus_large] -= 1

    def rangee(cellules: list[str]) -> str:
        return "  ".join(
            _ajuster(t, largeurs[i], etat.colonnes[i].type in ("montant", "nombre"))
            for i, t in enumerate(cellules)
        )

    entete = rangee([c.libelle for c in etat.colonnes])
    pages = [lignes[i : i + LIGNES_PAR_PAGE] for i in range(0, len(lignes), LIGNES_PAR_PAGE)] or [
        []
    ]
    flux = []
    for numero, contenu in enumerate(pages, start=1):
        textes = [
            etat.titre,
            etat.sous_titre,
            "",
            entete,
            "-" * len(entete),
            *(rangee(lg) for lg in contenu),
        ]
        y = HAUTEUR - MARGE
        ops = [b"BT", f"/F1 {TAILLE} Tf".encode()]
        for t in textes:
            ops.append(f"1 0 0 1 {MARGE} {y} Tm".encode() + b" (" + _texte_pdf(t) + b") Tj")
            y -= INTERLIGNE
        pied = f"{numero} / {len(pages)}"
        ops.append(f"1 0 0 1 {LARGEUR - MARGE - 40} {MARGE - 10} Tm".encode())
        ops.append(b"(" + _texte_pdf(pied) + b") Tj")
        ops.append(b"ET")
        flux.append(b"\n".join(ops))

    objets: list[bytes] = []
    n_pages = len(flux)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n_pages))
    objets.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objets.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    objets.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"
    )
    for i, page in enumerate(flux):
        objets.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {LARGEUR} {HAUTEUR}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode()
        )
        objets.append(f"<< /Length {len(page)} >>\nstream\n".encode() + page + b"\nendstream")
    sortie = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    positions = []
    for numero, objet in enumerate(objets, start=1):
        positions.append(len(sortie))
        sortie += f"{numero} 0 obj\n".encode() + objet + b"\nendobj\n"
    xref = len(sortie)
    sortie += f"xref\n0 {len(objets) + 1}\n0000000000 65535 f \n".encode()
    for p in positions:
        sortie += f"{p:010d} 00000 n \n".encode()
    sortie += (
        f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(sortie)
