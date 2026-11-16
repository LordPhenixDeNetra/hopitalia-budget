"""Vérifie que docker-compose.dokploy.yml décrit les services et volumes du module exactement comme
docker-compose.yml. Dokploy ne suit pas `include` : le fichier de la démonstration en ligne recopie ces
services, et cette vérification (job `docker` de la CI) empêche la copie de diverger.

À lancer depuis la racine du dépôt : python simulation/verifier_dokploy.py
"""

import json
import os
import subprocess
import sys

# Valeurs factices : seules les variables obligatoires (`:?`) doivent être renseignées.
FACTICES = {
    "POSTGRES_PASSWORD": "verification",
    "HOPITALIA_JWT_CLE": "verification",
    "SIMULATION_MOT_DE_PASSE": "verification",
}


def configuration(fichier: str) -> dict:
    sortie = subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            "verification",
            "-f",
            fichier,
            "config",
            "--format",
            "json",
        ],
        capture_output=True,
        encoding="utf-8",
        check=True,
        env=os.environ | FACTICES,
    )
    return json.loads(sortie.stdout)


def ecarts(module: dict, dokploy: dict) -> list[str]:
    trouves = [
        f"service {nom}"
        for nom, service in module["services"].items()
        if dokploy["services"].get(nom) != service
    ]
    trouves += [
        f"volume {nom}"
        for nom, volume in module.get("volumes", {}).items()
        if dokploy.get("volumes", {}).get(nom) != volume
    ]
    return trouves


if __name__ == "__main__":
    differents = ecarts(
        configuration("docker-compose.yml"), configuration("docker-compose.dokploy.yml")
    )
    if differents:
        print(
            "docker-compose.dokploy.yml diverge de docker-compose.yml : "
            + ", ".join(differents)
            + ". Reporter les changements de docker-compose.yml."
        )
        sys.exit(1)
    print("docker-compose.dokploy.yml reprend à l'identique les services du module.")
