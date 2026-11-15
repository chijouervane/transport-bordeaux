// Étape 2 : les requêtes find
// Lancer : mongosh "<URI>/transport_bordeaux" queries/02_find.js

print("1. Un document par son _id")
printjson(db.stations.findOne({ _id: ObjectId("6ad622cedd3a533fa6584133") }))

print("2. Un document par identifiant métier")
printjson(db.trips.findOne({ trip_id: "55408590-2027_HIVER-TR_A410-Lun-Mer-30" }, { line_name: 1, origin: 1, destination: 1, departure_time: 1, _id: 0 }))

print("3. Tri sur deux champs : par ligne, puis par heure de départ")
printjson(db.trips.find({}, { line_code: 1, departure_time: 1, _id: 0 }).sort({ line_code: 1, departure_time: 1 }).limit(5).toArray())

print("4. Trois documents, un seul champ affiché")
printjson(db.stations.find({}, { name: 1, _id: 0 }).limit(3).toArray())

print("5. $gt : trajets prévus en plus de 60 minutes")
print(db.trips.countDocuments({ scheduled_duration_min: { $gt: 60 } }))

print("6. $and : trams arrivés avec plus de 10 minutes de retard")
print(db.trips.countDocuments({ $and: [ { mode: "tram" }, { final_delay_min: { $gt: 10 } } ] }))

print("7. $regex : stations dont le nom commence par Sainte (sans limit)")
printjson(db.stations.find({ name: { $regex: /^Sainte/ } }, { name: 1, _id: 0 }).toArray())

print("Bonus. $expr : trajets plus longs que prévu")
print(db.trips.countDocuments({ $expr: { $gt: [ "$actual_duration_min", "$scheduled_duration_min" ] } }))