"""Accès MongoDB : connexion, collection validée, index, chargement."""
from __future__ import annotations

import logging
import time

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

from .config import SETTINGS, Settings, build_uri
from .transform import ALLOWED_VALUES

logger = logging.getLogger(__name__)

# Règles appliquées par MongoDB lui-même : tout document mal typé est refusé
ADMISSION_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["patient", "admission", "medical", "hospital", "billing"],
        "properties": {
            "patient": {
                "bsonType": "object",
                "required": ["name", "age", "gender", "blood_type"],
                "properties": {
                    "name": {"bsonType": "string", "minLength": 1},
                    "age": {"bsonType": "int", "minimum": 0, "maximum": 120},
                    "gender": {"enum": sorted(ALLOWED_VALUES["Gender"])},
                    "blood_type": {"enum": sorted(ALLOWED_VALUES["Blood Type"])},
                },
            },
            "admission": {
                "bsonType": "object",
                "required": ["admission_date", "discharge_date", "admission_type", "room_number"],
                "properties": {
                    "admission_date": {"bsonType": "date"},
                    "discharge_date": {"bsonType": "date"},
                    "length_of_stay_days": {"bsonType": "int", "minimum": 0},
                    "admission_type": {"enum": sorted(ALLOWED_VALUES["Admission Type"])},
                    "room_number": {"bsonType": "int", "minimum": 1},
                },
            },
            "medical": {
                "bsonType": "object",
                "required": ["condition", "medication", "test_results", "doctor"],
                "properties": {
                    "condition": {"bsonType": "string"},
                    "medication": {"bsonType": "string"},
                    "test_results": {"enum": sorted(ALLOWED_VALUES["Test Results"])},
                    "doctor": {"bsonType": "string"},
                },
            },
            "hospital": {"bsonType": "string", "minLength": 1},
            "billing": {
                "bsonType": "object",
                "required": ["amount", "insurance_provider"],
                "properties": {
                    "amount": {"bsonType": "decimal"},
                    "insurance_provider": {"bsonType": "string"},
                },
            },
        },
    }
}

# Les 5 index décidés à l'étape 3 (nom des champs, ordre, nom de l'index)
INDEXES = [
    ([("patient.name", ASCENDING)], "idx_patient_name"),
    ([("medical.condition", ASCENDING), ("admission.admission_date", DESCENDING)],
     "idx_condition_admission_date"),
    ([("admission.admission_date", ASCENDING)], "idx_admission_date"),
    ([("hospital", ASCENDING)], "idx_hospital"),
    ([("billing.insurance_provider", ASCENDING)], "idx_insurance_provider"),
]


def get_client(settings: Settings = SETTINGS, user=None, password=None,
               retries: int = 10, delay: float = 3.0) -> MongoClient:
    """Se connecte à MongoDB, en réessayant si la base n'est pas encore prête."""
    uri = build_uri(settings, user, password)
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            client[settings.database].command("ping")  # vérifie vraiment la connexion
            logger.info("Connecté à MongoDB %s:%s (tentative %s)", settings.host, settings.port, attempt)
            return client
        except (ConnectionFailure, OperationFailure) as exc:
            last_error = exc
            logger.warning("MongoDB indisponible (tentative %s/%s) : %s", attempt, retries, exc)
            time.sleep(delay)
    raise ConnectionError(f"Impossible de se connecter à MongoDB : {last_error}")


def prepare_collection(db, name: str):
    """Supprime puis recrée la collection avec ses règles (script relançable)."""
    if name in db.list_collection_names():
        db.drop_collection(name)
    db.create_collection(name, validator=ADMISSION_VALIDATOR,
                         validationLevel="strict", validationAction="error")
    return db[name]


def create_indexes(collection) -> list[str]:
    """Crée les index de la liste INDEXES."""
    return [collection.create_index(keys, name=name) for keys, name in INDEXES]


def insert_documents(collection, documents: list[dict], batch_size: int) -> int:
    """Insère les documents par paquets (moins de mémoire, moins d'allers-retours)."""
    inserted = 0
    for start in range(0, len(documents), batch_size):
        result = collection.insert_many(documents[start:start + batch_size], ordered=True)
        inserted += len(result.inserted_ids)
        logger.info("Lot inséré : %s/%s documents", inserted, len(documents))
    return inserted