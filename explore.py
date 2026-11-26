import pandas as pd

# 1. Lire le fichier et le mettre dans un tableau (DataFrame)
df = pd.read_csv("data/healthcare_dataset.csv")

print("=== Taille (lignes, colonnes) ===")
print(df.shape)

print("\n=== Types devinés par pandas ===")
print(df.dtypes)

print("\n=== 3 premières lignes ===")
print(df.head(3))

print("\n=== Cases vides par colonne ===")
print(df.isna().sum())

print("\n=== Lignes en double ===")
print(df.duplicated().sum())

print("\n=== Valeurs différentes des colonnes de catégories ===")
for col in ["Gender", "Blood Type", "Medical Condition", "Admission Type",
            "Medication", "Test Results", "Insurance Provider"]:
    print(col, ":", sorted(df[col].unique()))

print("\n=== Anomalies ===")
print("Montants négatifs :", (df["Billing Amount"] < 0).sum())
print("Noms mal écrits (casse) :", (df["Name"] != df["Name"].str.title()).sum())
print("Hôpitaux finissant par une virgule :", df["Hospital"].str.strip().str.endswith(",").sum())
admission = pd.to_datetime(df["Date of Admission"])
sortie = pd.to_datetime(df["Discharge Date"])
print("Sortie avant admission :", (sortie < admission).sum())
print("Âge min / max :", df["Age"].min(), "/", df["Age"].max())
print("Noms distincts après correction :", df["Name"].str.title().nunique())