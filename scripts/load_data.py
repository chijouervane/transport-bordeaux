"""Charge les trajets et les stations du réseau TBM dans MongoDB (base transport_bordeaux).

Source : GTFS TBM dézippé dans data/raw/. Les retards et les voyageurs sont simulés.
"""

import argparse
import csv
import os
import random
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from pprint import pprint
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pymongo import MongoClient

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Journée étudiée : le mardi 13 octobre 2026
SERVICE_DATE = date(2026, 10, 13)
PARIS = ZoneInfo("Europe/Paris")

# Lignes retenues, repérées par route_short_name
LINE_CODES = ["A", "B", "C", "D", "E", "F", "G", "H1", "H2", "951", "952", "953"]

# route_type GTFS -> mode
MODES = {"0": "tram", "3": "bus", "4": "bateau"}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def read_gtfs(name):
    """Lit un fichier GTFS ligne par ligne (générateur : rien n'est gardé en mémoire)."""
    with open(DATA_DIR / f"{name}.txt", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


# ---------------------------------------------------------------------------
# Étape 2 : calendrier et lignes
# ---------------------------------------------------------------------------

def active_services(day):
    """Renvoie l'ensemble des service_id qui circulent le jour donné."""
    day_str = day.strftime("%Y%m%d")  # format GTFS : AAAAMMJJ
    weekday = WEEKDAYS[day.weekday()]  # "tuesday" pour un mardi

    # 1. Services réguliers : jour dans la période et colonne du jour à 1
    services = {
        row["service_id"]
        for row in read_gtfs("calendar")
        if row["start_date"] <= day_str <= row["end_date"] and row[weekday] == "1"
    }

    # 2. Exceptions du jour : 1 = service ajouté, 2 = service retiré
    for row in read_gtfs("calendar_dates"):
        if row["date"] == day_str:
            if row["exception_type"] == "1":
                services.add(row["service_id"])
            elif row["exception_type"] == "2":
                services.discard(row["service_id"])

    return services


def load_routes():
    """Renvoie les lignes retenues : {route_id: {line_code, line_name, mode}}."""
    routes = {}
    for row in read_gtfs("routes"):
        if row["route_short_name"] in LINE_CODES and row["route_type"] in MODES:
            routes[row["route_id"]] = {
                "line_code": row["route_short_name"],
                "line_name": row["route_long_name"],
                "mode": MODES[row["route_type"]],
            }
    return routes


def load_trips(routes, services):
    """Renvoie les trajets retenus (bonne ligne et service actif) : {trip_id: ligne GTFS}."""
    return {
        row["trip_id"]: row
        for row in read_gtfs("trips")
        if row["route_id"] in routes and row["service_id"] in services
    }


# ---------------------------------------------------------------------------
# Étape 3 : stations
# ---------------------------------------------------------------------------

def load_stops():
    """Renvoie tous les points de stops.txt (stations et quais) : {stop_id: ligne GTFS}."""
    return {row["stop_id"]: row for row in read_gtfs("stops")}


def load_stop_times(trips):
    """Renvoie les passages des trajets retenus : {trip_id: [lignes GTFS triées par stop_sequence]}.

    stop_times.txt est lu ligne par ligne ; seules les lignes des trajets retenus sont gardées.
    """
    stop_times = {trip_id: [] for trip_id in trips}
    for row in read_gtfs("stop_times"):
        if row["trip_id"] in stop_times:
            stop_times[row["trip_id"]].append(row)
    for rows in stop_times.values():
        rows.sort(key=lambda r: int(r["stop_sequence"]))
    return stop_times


def build_stations(trips, routes, stops, stop_times):
    """Construit un document par station desservie par au moins un trajet retenu."""
    lines_by_station = {}  # station_code -> ensemble des lignes
    quays_by_station = {}  # station_code -> ensemble des quais desservis

    for trip_id, rows in stop_times.items():
        line_code = routes[trips[trip_id]["route_id"]]["line_code"]
        for row in rows:
            quay = stops[row["stop_id"]]
            station_code = quay["parent_station"]
            lines_by_station.setdefault(station_code, set()).add(line_code)
            quays_by_station.setdefault(station_code, set()).add(quay["stop_id"])

    stations = []
    for station_code, lines in sorted(lines_by_station.items()):
        station = stops[station_code]
        stations.append({
            "station_code": station_code,
            "name": station["stop_name"],
            "city_code": station["zone_id"],
            "lines": sorted(lines),
            "accessible": all(
                stops[q]["wheelchair_boarding"] == "1" for q in quays_by_station[station_code]
            ),
            "location": {
                "type": "Point",
                "coordinates": [float(station["stop_lon"]), float(station["stop_lat"])],
            },
            "daily_passengers": simulate_daily_passengers(len(lines)),
        })
    return stations


# ---------------------------------------------------------------------------
# Étape 4 : trajets et heures
# ---------------------------------------------------------------------------

def gtfs_seconds(hhmmss):
    """Convertit une heure GTFS "HH:MM:SS" en secondes depuis minuit (HH peut dépasser 23)."""
    h, m, s = hhmmss.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


# Minuit du jour de service, heure de Paris, exprimé en UTC
SERVICE_MIDNIGHT_UTC = datetime.combine(SERVICE_DATE, time(0), tzinfo=PARIS).astimezone(UTC)


def gtfs_to_utc(hhmmss):
    """Convertit une heure GTFS du jour de service en datetime UTC."""
    return SERVICE_MIDNIGHT_UTC + timedelta(seconds=gtfs_seconds(hhmmss))


def build_trips(trips, routes, stops, stop_times):
    """Construit un document par trajet, avec ses arrêts et les valeurs simulées."""
    documents = []
    for trip_id, trip in trips.items():
        route = routes[trip["route_id"]]
        rows = stop_times[trip_id]

        departure_time = gtfs_to_utc(rows[0]["departure_time"])
        departure_hour = departure_time.astimezone(PARIS).hour
        delays = simulate_delays(len(rows), departure_hour)

        trip_stops = []
        for i, row in enumerate(rows):
            # Au premier arrêt on prend l'heure de départ, ailleurs l'heure d'arrivée
            hhmmss = row["departure_time"] if i == 0 else row["arrival_time"]
            scheduled_time = gtfs_to_utc(hhmmss)
            station_code = stops[row["stop_id"]]["parent_station"]
            trip_stops.append({
                "order": int(row["stop_sequence"]),
                "station_code": station_code,
                "name": stops[station_code]["stop_name"],
                "scheduled_time": scheduled_time,
                "actual_time": scheduled_time + timedelta(minutes=delays[i]),
                "delay_min": delays[i],
            })

        first, last = trip_stops[0], trip_stops[-1]
        documents.append({
            "trip_id": trip_id,
            "line_code": route["line_code"],
            "line_name": route["line_name"],
            "mode": route["mode"],
            "origin": first["name"],
            "destination": trip["trip_headsign"] or last["name"],
            "departure_time": departure_time,
            "departure_hour": departure_hour,
            "scheduled_duration_min": minutes_between(first["scheduled_time"], last["scheduled_time"]),
            "actual_duration_min": minutes_between(first["actual_time"], last["actual_time"]),
            "final_delay_min": last["delay_min"],
            "passengers": simulate_passengers(route["mode"], departure_hour),
            "stops": trip_stops,
        })
    return documents


def minutes_between(start, end):
    """Écart entre deux datetimes, en minutes arrondies."""
    return round((end - start).total_seconds() / 60)


# ---------------------------------------------------------------------------
# Étape 5 : simulation (retards, voyageurs, fréquentation)
# ---------------------------------------------------------------------------

SEED = 42  # graine fixe : mêmes valeurs à chaque exécution

# Probabilité de prendre 1 minute de retard entre deux arrêts
DELAY_PROBABILITY_PEAK = 0.25
DELAY_PROBABILITY_OFF_PEAK = 0.08

# Voyageurs moyens par trajet (heure creuse) ; multiplié aux heures de pointe
BASE_PASSENGERS = {"tram": 250, "bus": 80, "bateau": 40}
PEAK_FACTOR = 1.8

# Voyageurs par jour apportés par chaque ligne qui dessert une station
PASSENGERS_PER_LINE = 2000


def is_peak_hour(hour):
    """Heures de pointe : 7 h–9 h et 17 h–19 h (heure locale)."""
    return 7 <= hour < 9 or 17 <= hour < 19


def simulate_delays(n_stops, hour):
    """Retard cumulé (en minutes) à chaque arrêt : 0 au départ, puis +0 ou +1 par arrêt."""
    probability = DELAY_PROBABILITY_PEAK if is_peak_hour(hour) else DELAY_PROBABILITY_OFF_PEAK
    delays = [0]
    for _ in range(n_stops - 1):
        increment = 1 if random.random() < probability else 0
        delays.append(delays[-1] + increment)
    return delays


def simulate_passengers(mode, hour):
    """Personnes montées pendant le trajet : moyenne du mode, ±40 %, plus aux heures de pointe."""
    passengers = BASE_PASSENGERS[mode] * random.uniform(0.6, 1.4)
    if is_peak_hour(hour):
        passengers *= PEAK_FACTOR
    return round(passengers)


def simulate_daily_passengers(n_lines):
    """Fréquentation journalière d'une station : proportionnelle au nombre de lignes, ±50 %."""
    return round(PASSENGERS_PER_LINE * n_lines * random.uniform(0.5, 1.5))


# ---------------------------------------------------------------------------
# Étape 6 : construction complète et vérifications (--dry-run)
# ---------------------------------------------------------------------------

def build_documents():
    """Lit le GTFS et renvoie (trajets, stations), prêts à être insérés."""
    random.seed(SEED)
    services = active_services(SERVICE_DATE)
    routes = load_routes()
    trips = load_trips(routes, services)
    stops = load_stops()
    stop_times = load_stop_times(trips)
    stations = build_stations(trips, routes, stops, stop_times)
    trip_docs = build_trips(trips, routes, stops, stop_times)
    return trip_docs, stations


def check(label, actual, expected):
    """Affiche une vérification et renvoie True si la valeur obtenue est celle attendue."""
    ok = actual == expected
    print(f"  [{'OK' if ok else 'ÉCHEC'}] {label} : {actual!r}" + ("" if ok else f" (attendu {expected!r})"))
    return ok


def verify(trip_docs, stations):
    """Compare quelques valeurs connues du GTFS avec les documents construits."""
    trip = next(t for t in trip_docs if t["trip_id"] == "55408590-2027_HIVER-TR_A410-Lun-Mer-30")
    station = next(s for s in stations if s["station_code"] == "TSJEAN")

    print("Vérifications :")
    results = [
        check("nombre de trajets", len(trip_docs), 2503),
        check("nombre de stations", len(stations), 262),
        check("trajet témoin : ligne", trip["line_code"], "C"),
        check("trajet témoin : mode", trip["mode"], "tram"),
        check("trajet témoin : origine", trip["origin"], "Villenave Pyrénées"),
        check("trajet témoin : destination", trip["destination"], "Parc des Expositions"),
        check("trajet témoin : nombre d'arrêts", len(trip["stops"]), 30),
        check("trajet témoin : départ (UTC)", trip["departure_time"].isoformat().replace("+00:00", "Z"),
              "2026-10-13T05:55:44Z"),
        check("trajet témoin : departure_hour", trip["departure_hour"], 7),
        check("trajet témoin : scheduled_duration_min", trip["scheduled_duration_min"], 53),
        check("TSJEAN : nom", station["name"], "Gare Saint-Jean"),
        check("TSJEAN : city_code", station["city_code"], "33063"),
        check("TSJEAN : lignes", station["lines"], ["C", "D", "F"]),
    ]
    return all(results)


# ---------------------------------------------------------------------------
# Étape 7 : chargement dans MongoDB Atlas
# ---------------------------------------------------------------------------

DATABASE = "transport_bordeaux"


def connect():
    """Ouvre la connexion à Atlas avec l'adresse lue dans .env (jamais écrite dans le code)."""
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    uri = os.getenv("MONGODB_URI")
    if not uri:
        sys.exit("MONGODB_URI absent : copier .env.example en .env et le renseigner.")
    client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
    client.admin.command("ping")  # échoue tout de suite si Atlas est injoignable
    return client


def load(db, trip_docs, stations):
    """Vide trips et stations, puis insère les nouveaux documents."""
    for name, documents in (("trips", trip_docs), ("stations", stations)):
        collection = db[name]
        deleted = collection.delete_many({}).deleted_count
        inserted = len(collection.insert_many(documents).inserted_ids)
        print(f"  {name} : {deleted} supprimés, {inserted} insérés")


def show_summary(db):
    """Affiche le nombre de documents de chaque collection et un exemple de chacune."""
    for name in ("trips", "stations"):
        print(f"\n{name} : {db[name].count_documents({})} documents")
        # Pour un trajet, on n'affiche que les 2 premiers arrêts ($slice)
        projection = {"stops": {"$slice": 2}} if name == "trips" else None
        pprint(db[name].find_one({}, projection), sort_dicts=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="construit les documents et les vérifie, sans se connecter à MongoDB")
    args = parser.parse_args()

    trip_docs, stations = build_documents()
    if not verify(trip_docs, stations):
        sys.exit("Les vérifications ont échoué : rien n'est chargé.")

    if args.dry_run:
        print("\nExemple de trajet (sans ses arrêts) :")
        pprint({k: v for k, v in trip_docs[0].items() if k != "stops"}, sort_dicts=False)
        print("Premier arrêt :")
        pprint(trip_docs[0]["stops"][0], sort_dicts=False)
        print("Exemple de station :")
        pprint(stations[0], sort_dicts=False)
        print("\n--dry-run : aucune connexion à MongoDB.")
        return

    client = connect()
    db = client[DATABASE]
    print(f"\nChargement dans la base {DATABASE} :")
    load(db, trip_docs, stations)
    show_summary(db)
    client.close()


if __name__ == "__main__":
    main()
