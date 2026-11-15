// Étape 4 : la référence
// Lancer : mongosh "<URI>/transport_bordeaux" queries/04_reference.js
// À lancer une seule fois : insertMany échoue si les _id 3, 4 et 6 existent déjà

print("1. La troisième collection : _id = nombre de lettres du mode")
printjson(db.transport_modes.insertMany([
  { _id: 3, name: "bus", description: "Bus express à haut niveau de service", lines: [
    { code: "G", name: "BUS EXPRESS G", color: "#006685" },
    { code: "H1", name: "BUS EXPRESS H1", color: "#006685" },
    { code: "H2", name: "BUS EXPRESS H2", color: "#006685" }
  ] },
  { _id: 4, name: "tram", description: "Tramway, lignes A à F", lines: [
    { code: "A", name: "Tram A", color: "#831F82" },
    { code: "B", name: "Tram B", color: "#E50040" },
    { code: "C", name: "Tram C", color: "#D35098" },
    { code: "D", name: "Tram D", color: "#9262A3" },
    { code: "E", name: "Tram E", color: "#967651" },
    { code: "F", name: "Tram F", color: "#F08700" }
  ] },
  { _id: 6, name: "bateau", description: "Navette fluviale sur la Garonne", lines: [
    { code: "951", name: "LE BATO 1", color: "#006BB5" },
    { code: "952", name: "LE BATO 2", color: "#006BB5" },
    { code: "953", name: "LE BATO 3", color: "#006BB5" }
  ] }
]))

print("2. La référence, créée par un update : mode_id = nombre de lettres du champ mode")
printjson(db.trips.updateMany({}, [ { $set: { mode_id: { $strLenCP: "$mode" } } } ]))

print("3. Vérification : nombre de trajets par mode et par mode_id")
printjson(db.trips.aggregate([
  { $group: { _id: { mode: "$mode", mode_id: "$mode_id" }, trajets: { $sum: 1 } } }
]).toArray())

print("4. Le trajet (parent) avec son mode (enfant)")
printjson(db.trips.aggregate([
  { $match: { trip_id: "55408590-2027_HIVER-TR_A410-Lun-Mer-30" } },
  { $lookup: { from: "transport_modes", localField: "mode_id", foreignField: "_id", as: "mode_details" } },
  { $project: { _id: 0, line_name: 1, origin: 1, destination: 1, mode_id: 1, mode_details: 1 } }
]).toArray())