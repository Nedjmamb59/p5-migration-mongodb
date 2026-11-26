"""Contrôles d'intégrité APRÈS migration."""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def compare_with_source(collection, clean_df) -> dict:
    """Compare la base au CSV nettoyé. Renvoie {controle: True/False}."""
    checks = {}

    # 1. Autant de documents que de lignes nettoyées
    checks["count"] = collection.count_documents({}) == len(clean_df)

    # 2. Aucun champ obligatoire vide
    required = ["patient.name", "patient.age", "patient.gender", "patient.blood_type",
                "admission.admission_date", "admission.discharge_date", "admission.admission_type",
                "admission.room_number", "medical.condition", "medical.medication",
                "medical.test_results", "medical.doctor", "hospital",
                "billing.amount", "billing.insurance_provider"]
    checks["no_missing_fields"] = collection.count_documents(
        {"$or": [{f: None} for f in required]}) == 0

    # 3. Les mêmes catégories des deux côtés
    pairs = {"medical.condition": "Medical Condition", "medical.medication": "Medication",
             "patient.blood_type": "Blood Type", "billing.insurance_provider": "Insurance Provider",
             "admission.admission_type": "Admission Type", "medical.test_results": "Test Results"}
    checks["same_categories"] = all(set(collection.distinct(m)) == set(clean_df[c].unique())
                                    for m, c in pairs.items())

    # 4. La somme facturée identique au centime
    agg = list(collection.aggregate([{"$group": {"_id": None, "total": {"$sum": "$billing.amount"}}}]))
    mongo_total = agg[0]["total"].to_decimal() if agg else Decimal(0)
    csv_total = sum(Decimal(str(v)).quantize(Decimal("0.01")) for v in clean_df["Billing Amount"])
    checks["billing_total"] = abs(mongo_total - csv_total) <= Decimal("0.01")

    # 5. Les bons types sur tous les documents
    type_filter = {"patient.age": {"$type": "int"}, "admission.admission_date": {"$type": "date"},
                   "admission.room_number": {"$type": "int"}, "billing.amount": {"$type": "decimal"}}
    checks["bson_types"] = collection.count_documents(type_filter) == len(clean_df)

    for name, ok in checks.items():
        logger.info("Contrôle post-migration %-18s : %s", name, "OK" if ok else "ÉCHEC")
    return checks