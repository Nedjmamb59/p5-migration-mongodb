# Journal de bord

## Étape 1 — Mise en place
- Outils installés : Python 3.13, Git, Docker Desktop (WSL 2 et hyperviseur à activer), VS Code.
- Projet créé, environnement virtuel, requirements.txt, .gitignore, .env.

## Étape 2 — Audit du dataset (explore.py)
- 55 500 lignes, 15 colonnes, aucune valeur manquante.
- 534 doublons stricts → à supprimer.
- 55 467 noms avec une casse irrégulière → à normaliser.
- 4 776 noms d'hôpitaux finissant par une virgule → à corriger.
- 108 montants négatifs → conservés, question à poser au client.
- Dates lues comme du texte → à convertir en dates.
- Montants à 15 décimales → arrondir au centime, type décimal.
- Pas d'identifiant patient (40 235 noms distincts) → une collection de séjours.
## Étape 3 — Modèle de données
- Base `healthcare`, collection `admissions`, 1 document = 1 séjour.
- Sous-documents : patient, admission, medical, billing (+ hospital).
- Pas de collection patients : aucun identifiant patient fiable.
- Types : âge et chambre en int, dates en date, montant en décimal, catégories en liste autorisée.
- 5 index : nom, pathologie + date, date, hôpital, assureur.