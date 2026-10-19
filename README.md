# Transport Bordeaux

Projet NoSQL (Efrei) — base MongoDB `transport_bordeaux` hébergée sur MongoDB Atlas.

La base enregistre les trajets des trams (A à F), des bus express (G, H1, H2) et des
navettes fluviales Bato (951, 952, 953) de Bordeaux sur une journée, le mardi
13 octobre 2026, afin d'étudier quelles lignes prennent du retard et à quelles heures.

Elle contient deux collections :

- `trips` : un document par trajet (un aller d'un terminus à l'autre), avec ses arrêts ;
- `stations` : un document par station desservie.

Les noms de champs sont en anglais, les valeurs en français.

## Source des données

- Horaires, lignes et stations : fichier GTFS du réseau TBM (Bordeaux Métropole),
  version du 9 octobre 2026, dézippé dans `data/raw/` (non versionné).
- **Les retards, le nombre de voyageurs par trajet et la fréquentation des stations
  sont simulés** (graine aléatoire fixe, résultats reproductibles).

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # puis renseigner l'adresse du cluster Atlas
```

## Chargement

```bash
python scripts/load_data.py --dry-run   # construit les documents sans se connecter
python scripts/load_data.py             # vide puis remplit trips et stations
```

## Organisation

| Dossier      | Contenu                                           |
| ------------ | ------------------------------------------------- |
| `data/raw/`  | GTFS dézippé (non versionné)                      |
| `scripts/`   | script de chargement `load_data.py`               |
| `queries/`   | requêtes des étapes 2 à 6 du sujet                |
| `dump/`      | sauvegardes `mongodump` (non versionné)           |
| `docs/`      | documentation du projet                           |
