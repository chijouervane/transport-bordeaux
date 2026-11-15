// Étape 3 : les updates
// À lancer UNE seule fois, après le dump : mongodump --uri "<URI>/transport_bordeaux" --out dump/00_initial

print("1. Premier document d'un filtre qui en renvoie plusieurs")
printjson(db.stations.updateOne({ city_code: "33063" }, { $set: { accessible: false } }))

print("2. Incrémenter une valeur dans tous les documents")
printjson(db.trips.updateMany({}, { $inc: { scheduled_duration_min: 2 } }))

print("3. Ajouter un élément à un tableau d'objets imbriqués")
printjson(db.trips.updateOne(
  { trip_id: "55408590-2027_HIVER-TR_A410-Lun-Mer-30" },
  { $push: { stops: {
      order: 31, station_code: "TSJEAN", name: "Gare Saint-Jean",
      scheduled_time: new Date("2026-10-13T06:55:00Z"),
      actual_time: new Date("2026-10-13T07:01:00Z"),
      delay_min: 6
  } } }
))

print("4. Renommer un champ dans tous les documents")
printjson(db.stations.updateMany({}, { $rename: { accessible: "wheelchair_accessible" } }))

print("5. Supprimer toutes les valeurs d'une collection (sur une copie)")
db.trips.aggregate([{ $out: "trips_copy" }])
printjson(db.trips_copy.deleteMany({}))