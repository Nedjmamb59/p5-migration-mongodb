"""Démonstration des opérations CRUD : python -m app.crud_demo

Utilise le compte de l'application (APP_USER) : il peut créer, lire et modifier,
mais PAS supprimer. On montre que la suppression lui est refusée, puis on
supprime avec le compte de migration.
"""
import logging
import os
from datetime import datetime
from pprint import pformat

from pymongo.errors import OperationFailure

from .config import SETTINGS
from .database import get_client
from .transform import to_money

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s | %(message)s")
logger = logging.getLogger("crud")

DEMO_TAG = "crud-demo"  # étiquette pour retrouver le document de démonstration


def create(collection):
    """CREATE : ajoute un séjour fictif (vérifié par les règles de MongoDB)."""
    doc = {
        "patient": {"name": "Jane Demo", "age": 42, "gender": "Female", "blood_type": "O+"},
        "admission": {"admission_date": datetime(2026, 11, 2), "discharge_date": datetime(2026, 11, 6),
                      "length_of_stay_days": 4, "admission_type": "Elective", "room_number": 101},
        "medical": {"condition": "Asthma", "medication": "Ibuprofen",
                    "test_results": "Normal", "doctor": "John Smith"},
        "hospital": "DataSoluTech General",
        "billing": {"amount": to_money(1234.5), "insurance_provider": "Aetna"},
        "source": DEMO_TAG,
    }
    inserted_id = collection.insert_one(doc).inserted_id
    logger.info("CREATE -> document créé, _id=%s", inserted_id)


def read(collection):
    """READ : trois façons de lire."""
    # 1. Un document précis, en n'affichant que certains champs (projection)
    doc = collection.find_one({"source": DEMO_TAG}, {"_id": 0, "patient": 1, "medical": 1})
    logger.info("READ document de démo :\n%s", pformat(doc))
    # 2. Un comptage avec filtre
    n = collection.count_documents({"medical.condition": "Diabetes",
                                    "admission.admission_date": {"$gte": datetime(2023, 1, 1)}})
    logger.info("READ patients diabétiques admis depuis 2023 : %s", n)
    # 3. Une agrégation : nombre de séjours et durée moyenne par pathologie
    pipeline = [
        {"$group": {"_id": "$medical.condition", "sejours": {"$sum": 1},
                    "duree_moyenne": {"$avg": "$admission.length_of_stay_days"}}},
        {"$sort": {"sejours": -1}},
    ]
    for row in collection.aggregate(pipeline):
        logger.info("READ %-13s séjours=%-6s durée moyenne=%.1f jours",
                    row["_id"], row["sejours"], row["duree_moyenne"])


def update(collection):
    """UPDATE : modifie le résultat d'examen du séjour de démonstration."""
    res = collection.update_one({"source": DEMO_TAG}, {"$set": {"medical.test_results": "Abnormal"}})
    logger.info("UPDATE -> %s document(s) modifié(s)", res.modified_count)


def delete(collection):
    """DELETE : supprime le séjour de démonstration."""
    res = collection.delete_many({"source": DEMO_TAG})
    logger.info("DELETE -> %s document(s) supprimé(s)", res.deleted_count)


def main():
    """Enchaîne Create, Read, Update avec APP_USER, puis teste Delete."""
    app_client = get_client(user=os.getenv("APP_USER"), password=os.getenv("APP_PASSWORD"))
    admin_client = get_client()  # compte de migration
    try:
        app_col = app_client[SETTINGS.database][SETTINGS.collection]
        create(app_col)
        read(app_col)
        update(app_col)
        try:
            delete(app_col)
        except OperationFailure as exc:
            logger.info("DELETE refusé pour APP_USER (attendu) : %s", exc.details.get("errmsg"))
        delete(admin_client[SETTINGS.database][SETTINGS.collection])
    finally:
        app_client.close()
        admin_client.close()


if __name__ == "__main__":
    main()