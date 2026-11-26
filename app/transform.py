"""Extraction et transformation du CSV en documents MongoDB."""
from __future__ import annotations

import logging
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd
from bson.decimal128 import Decimal128

logger = logging.getLogger(__name__)

# Colonnes attendues dans le CSV (le "contrat" avec le client)
EXPECTED_COLUMNS = [
    "Name", "Age", "Gender", "Blood Type", "Medical Condition",
    "Date of Admission", "Doctor", "Hospital", "Insurance Provider",
    "Billing Amount", "Room Number", "Admission Type", "Discharge Date",
    "Medication", "Test Results",
]

# Valeurs autorisées (reprises plus tard dans les règles de MongoDB)
ALLOWED_VALUES = {
    "Gender": {"Male", "Female"},
    "Blood Type": {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"},
    "Admission Type": {"Urgent", "Emergency", "Elective"},
    "Test Results": {"Normal", "Abnormal", "Inconclusive"},
}

# Colonnes de texte, à nettoyer des espaces superflus
TEXT_COLUMNS = ["Name", "Gender", "Blood Type", "Medical Condition", "Doctor", "Hospital",
                "Insurance Provider", "Admission Type", "Medication", "Test Results"]


def load_csv(path: str) -> pd.DataFrame:
    """Lit le CSV en forçant tout en texte : c'est nous qui typons ensuite."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    logger.info("CSV chargé : %s lignes, %s colonnes (%s)", len(df), df.shape[1], path)
    return df


def audit_dataframe(df: pd.DataFrame) -> dict:
    """Rapport d'intégrité AVANT migration. Arrête tout si une colonne manque."""
    missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Colonnes manquantes dans le CSV : {missing_cols}")

    report = {
        "rows": len(df),
        "columns": list(df.columns),
        "missing_values": {c: int(n) for c, n in df.isna().sum().items() if n},
        "exact_duplicates": int(df.duplicated().sum()),
        "non_numeric": {}, "invalid_dates": {}, "unexpected_categories": {},
    }
    for col in ("Age", "Room Number", "Billing Amount"):
        bad = pd.to_numeric(df[col], errors="coerce").isna() & df[col].notna()
        if bad.any():
            report["non_numeric"][col] = int(bad.sum())
    for col in ("Date of Admission", "Discharge Date"):
        bad = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce").isna()
        if bad.any():
            report["invalid_dates"][col] = int(bad.sum())
    for col, allowed in ALLOWED_VALUES.items():
        unexpected = set(df[col].dropna().str.strip().unique()) - allowed
        if unexpected:
            report["unexpected_categories"][col] = sorted(unexpected)
    billing = pd.to_numeric(df["Billing Amount"], errors="coerce")
    report["negative_billing"] = int((billing < 0).sum())
    return report

def _normalize_hospital(value: str) -> str:
    """Supprime la virgule parasite en fin de nom d'hôpital."""
    return value.strip().rstrip(",").strip()


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoie, type, puis supprime les doublons stricts."""
    out = df.copy()
    for col in TEXT_COLUMNS:
        out[col] = out[col].str.strip()
    out["Name"] = out["Name"].str.title()
    out["Hospital"] = out["Hospital"].map(_normalize_hospital)

    out["Age"] = pd.to_numeric(out["Age"], errors="raise").astype("int64")
    out["Room Number"] = pd.to_numeric(out["Room Number"], errors="raise").astype("int64")
    out["Billing Amount"] = pd.to_numeric(out["Billing Amount"], errors="raise").astype("float64")
    out["Date of Admission"] = pd.to_datetime(out["Date of Admission"], format="%Y-%m-%d")
    out["Discharge Date"] = pd.to_datetime(out["Discharge Date"], format="%Y-%m-%d")

    before = len(out)
    out = out.drop_duplicates().reset_index(drop=True)
    logger.info("Doublons stricts supprimés : %s", before - len(out))
    return out


def to_money(value: float) -> Decimal128:
    """Montant arrondi au centime, en décimal exact."""
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Decimal128(amount)


def row_to_document(row: dict) -> dict:
    """Une ligne nettoyée devient un document imbriqué (un séjour)."""
    admission_date: datetime = row["Date of Admission"].to_pydatetime()
    discharge_date: datetime = row["Discharge Date"].to_pydatetime()
    return {
        "patient": {"name": row["Name"], "age": int(row["Age"]),
                    "gender": row["Gender"], "blood_type": row["Blood Type"]},
        "admission": {
            "admission_date": admission_date,
            "discharge_date": discharge_date,
            "length_of_stay_days": (discharge_date - admission_date).days,
            "admission_type": row["Admission Type"],
            "room_number": int(row["Room Number"]),
        },
        "medical": {"condition": row["Medical Condition"], "medication": row["Medication"],
                    "test_results": row["Test Results"], "doctor": row["Doctor"]},
        "hospital": row["Hospital"],
        "billing": {"amount": to_money(row["Billing Amount"]),
                    "insurance_provider": row["Insurance Provider"]},
    }


def to_documents(df: pd.DataFrame) -> list[dict]:
    """Convertit tout le tableau nettoyé en liste de documents."""
    return [row_to_document(row) for row in df.to_dict(orient="records")]