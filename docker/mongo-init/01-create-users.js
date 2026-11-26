// Exécuté UNE SEULE FOIS par l'image officielle mongo, au tout premier démarrage.
// Le compte root est déjà créé par l'image. Les mots de passe viennent du .env.
const dbName = process.env.MONGO_INITDB_DATABASE || "healthcare";
const collName = process.env.MONGO_COLLECTION || "admissions";
const appDb = db.getSiblingDB(dbName);

// Rôle sur mesure : lire, créer, modifier, mais PAS supprimer
appDb.createRole({
  role: "admissionsWriter",
  privileges: [{ resource: { db: dbName, collection: collName },
                 actions: ["find", "insert", "update"] }],
  roles: [],
});

const users = [
  { user: process.env.MIGRATION_USER, pwd: process.env.MIGRATION_PASSWORD,
    roles: [{ role: "readWrite", db: dbName }, { role: "dbAdmin", db: dbName }] },
  { user: process.env.ANALYST_USER, pwd: process.env.ANALYST_PASSWORD,
    roles: [{ role: "read", db: dbName }] },
  { user: process.env.APP_USER, pwd: process.env.APP_PASSWORD,
    roles: [{ role: "admissionsWriter", db: dbName }] },
  { user: process.env.DB_ADMIN_USER, pwd: process.env.DB_ADMIN_PASSWORD,
    roles: [{ role: "dbOwner", db: dbName }] },
];

users.forEach((u) => {
  if (!u.user || !u.pwd) {
    throw new Error("Variable d'environnement manquante (voir .env.example)");
  }
  appDb.createUser({ ...u, mechanisms: ["SCRAM-SHA-256"] });
  print(`Utilisateur créé : ${u.user}`);
});