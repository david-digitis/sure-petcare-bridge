# Projet : Sure Petcare MQTT Bridge

## Quoi

Pont Docker leger qui connecte les appareils **Sure Petcare** (chatieres,
portes pour animaux) a **[Gladys Assistant](https://gladysassistant.com)**
via **MQTT**.

Poll l'API cloud Sure Petcare avec [surepy](https://github.com/benleb/surepy)
(la lib qu'utilisait Home Assistant) et publie l'etat pets/devices sur les
topics MQTT Gladys :
- Localisation animal (dedans/dehors) → capteur de presence binaire
- Niveau batterie chatiere → capteur pourcentage
- Auto-decouverte de tous les pets et chatieres du compte
- Log intelligent : seulement les changements d'etat, pas chaque poll
- ~50 Mo RAM, image Docker multi-arch (amd64 + arm64)

## Stack

- **Python** — point d'entree `bridge.py`, deps dans `requirements.txt`
  (surepy, paho-mqtt)
- **Docker** — `Dockerfile`, image publiee sur `ghcr.io/david-digitis/sure-petcare-bridge`
- **CI** — `.github/workflows/docker.yml` (build + push image multi-arch)

## Etat

Projet **stable / termine**. Fonctionnel, image publiee, CI verte. Pas de
developpement actif prevu — interventions = maintenance (bump deps, fix API
Sure Petcare si elle casse).

## Securite

- **Aucun secret dans le repo.** Credentials Sure Petcare (`SUREPETCARE_EMAIL`,
  `SUREPETCARE_PASSWORD`) et config MQTT passes **uniquement en variables
  d'environnement Docker** au `docker run`. Ne jamais les ecrire en dur ni
  dans un compose committe.
- Repo **public** `david-digitis/sure-petcare-bridge` — toute contribution
  doit rester sans identifiants.

## Lancer

```bash
docker run -d --name sure-petcare-bridge --network host --restart unless-stopped \
  -e SUREPETCARE_EMAIL=... -e SUREPETCARE_PASSWORD=... \
  -e MQTT_HOST=localhost -e MQTT_PORT=1883 -e POLL_INTERVAL=60 \
  ghcr.io/david-digitis/sure-petcare-bridge:latest
```

## Liens

- Repo : <https://github.com/david-digitis/sure-petcare-bridge> (public)
- Gladys : <https://gladysassistant.com>
- surepy : <https://github.com/benleb/surepy>
