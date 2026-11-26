"""Point d'entrée de la migration : python -m app.migrate"""
import argparse
import json
import logging
import sys
import time

from .config import SETTINGS
from .database import create_indexes, get_client, insert_documents, prepare_collection
from .integrity import compare_with_source
from .transform import audit_dataframe, clean_dataframe, load_csv, to_documents

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
logger = logging.getLogger("migration")


def parse_args(argv=None):
    """Lit les options de la ligne de commande (chemin du CSV, taille des lots)."""
    parser = argparse.ArgumentParser(description="Migration du dataset médical vers MongoDB")
    parser.add_argument("--csv", default=SETTINGS.csv_path)
    parser.add_argument("--batch-size", type=int, default=SETTINGS.batch_size)
    return parser.parse_args(argv)


def run(csv_path: str, batch_size: int) -> bool:
    """Enchaîne toutes les étapes de la migration."""
    start = time.perf_counter()
    raw = load_csv(csv_path)                                   # 1. lire
    report = audit_dataframe(raw)                              # 2. auditer
    logger.info("Audit avant migration :\n%s", json.dumps(
        {k: v for k, v in report.items() if k != "columns"}, indent=2, ensure_ascii=False))
    clean = clean_dataframe(raw)                               # 3. nettoyer
    documents = to_documents(clean)                            # 4. créer les documents

    client = get_client()
    try:
        collection = prepare_collection(client[SETTINGS.database], SETTINGS.collection)
        inserted = insert_documents(collection, documents, batch_size)   # 5. charger
        create_indexes(collection)                                       # 6. indexer
        checks = compare_with_source(collection, clean)                  # 7. contrôler
    finally:
        client.close()

    success = all(checks.values())
    logger.info("Migration %s : %s lignes lues, %s doublons écartés, %s documents insérés en %.1f s",
                "RÉUSSIE" if success else "EN ÉCHEC", len(raw), len(raw) - len(clean),
                inserted, time.perf_counter() - start)
    return success


def main(argv=None) -> int:
    """Renvoie 0 si tout va bien, 1 sinon."""
    args = parse_args(argv)
    try:
        return 0 if run(args.csv, args.batch_size) else 1
    except Exception:
        logger.exception("Erreur fatale pendant la migration")
        return 1


if __name__ == "__main__":
    sys.exit(main())