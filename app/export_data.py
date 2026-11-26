"""Exporte toute la collection en JSON et en CSV : python -m app.export_data"""
import csv
import logging
import os
from datetime import datetime

from bson import json_util

from .config import SETTINGS
from .database import get_client

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s | %(message)s")
logger = logging.getLogger("export")

# Colonne du CSV d'origine -> champ dans MongoDB
CSV_FIELDS = {
    "Name": "patient.name", "Age": "patient.age", "Gender": "patient.gender",
    "Blood Type": "patient.blood_type", "Medical Condition": "medical.condition",
    "Date of Admission": "admission.admission_date", "Doctor": "medical.doctor",
    "Hospital": "hospital", "Insurance Provider": "billing.insurance_provider",
    "Billing Amount": "billing.amount", "Room Number": "admission.room_number",
    "Admission Type": "admission.admission_type", "Discharge Date": "admission.discharge_date",
    "Medication": "medical.medication", "Test Results": "medical.test_results",
}


def _get(doc: dict, dotted: str):
    """Lit une valeur imbriquée avec un chemin comme 'patient.name'."""
    value = doc
    for key in dotted.split("."):
        value = value[key]
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "to_decimal"):
        return str(value.to_decimal())
    return value


def export_json(collection, path: str) -> int:
    """Un document par ligne, en JSON étendu (les types sont conservés)."""
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for doc in collection.find():
            fh.write(json_util.dumps(doc) + "\n")
            n += 1
    return n


def export_csv(collection, path: str) -> int:
    """Au format des colonnes d'origine (à plat)."""
    n = 0
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_FIELDS.keys())
        for doc in collection.find({}, {"_id": 0}):
            writer.writerow(_get(doc, f) for f in CSV_FIELDS.values())
            n += 1
    return n


def main():
    os.makedirs(SETTINGS.export_dir, exist_ok=True)
    client = get_client()
    try:
        col = client[SETTINGS.database][SETTINGS.collection]
        n_json = export_json(col, os.path.join(SETTINGS.export_dir, "admissions.jsonl"))
        n_csv = export_csv(col, os.path.join(SETTINGS.export_dir, "admissions.csv"))
        logger.info("Export terminé : %s documents JSON, %s lignes CSV -> %s",
                    n_json, n_csv, SETTINGS.export_dir)
    finally:
        client.close()


if __name__ == "__main__":
    main()