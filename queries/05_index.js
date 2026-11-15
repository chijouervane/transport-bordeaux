// Étape 5 : les index
// Lancer : mongosh "<URI>/transport_bordeaux" queries/05_index.js

function docsLus(curseur) {
  return curseur.explain("executionStats").executionStats.totalDocsExamined
}

print("1. Index composé : ligne puis retard décroissant")
print("Avant : " + docsLus(db.trips.find({ line_code: "C" }).sort({ final_delay_min: -1 })) + " documents lus")
db.trips.createIndex({ line_code: 1, final_delay_min: -1 }, { name: "idx_line_delay" })
print("Après : " + docsLus(db.trips.find({ line_code: "C" }).sort({ final_delay_min: -1 })) + " documents lus")

print("2. Index sur le tableau des arrêts (multikey)")
print("Avant : " + docsLus(db.trips.find({ "stops.station_code": "TSJEAN" })) + " documents lus")
db.trips.createIndex({ "stops.station_code": 1 }, { name: "idx_trip_stations" })
print("Après : " + docsLus(db.trips.find({ "stops.station_code": "TSJEAN" })) + " documents lus")

print("3. Index unique sur le code de station")
print("Avant : " + docsLus(db.stations.find({ station_code: "TSJEAN" })) + " documents lus")
db.stations.createIndex({ station_code: 1 }, { unique: true, name: "idx_station_code" })
print("Après : " + docsLus(db.stations.find({ station_code: "TSJEAN" })) + " documents lus")