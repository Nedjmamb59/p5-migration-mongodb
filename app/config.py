"""Configuration centralisée, lue depuis les variables d'environnement."""
import os
from dataclasses import dataclass
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()  # lit le fichier .env (dans Docker, les variables arrivent autrement)


@dataclass(frozen=True)
class Settings:
    """Tous les réglages du projet, regroupés au même endroit."""

    host: str = os.getenv("MONGO_HOST", "localhost")
    port: int = int(os.getenv("MONGO_PORT", "27017"))
    database: str = os.getenv("MONGO_DB", "healthcare")
    collection: str = os.getenv("MONGO_COLLECTION", "admissions")
    user: str = os.getenv("MIGRATION_USER", "")          # compte du script de migration
    password: str = os.getenv("MIGRATION_PASSWORD", "")
    auth_db: str = os.getenv("MONGO_AUTH_DB", os.getenv("MONGO_DB", "healthcare"))
    csv_path: str = os.getenv("CSV_PATH", "data/healthcare_dataset.csv")
    export_dir: str = os.getenv("EXPORT_DIR", "exports")
    batch_size: int = int(os.getenv("BATCH_SIZE", "5000"))


def build_uri(settings: Settings, user: str | None = None, password: str | None = None) -> str:
    """Construit l'adresse de connexion à MongoDB."""
    user = settings.user if user is None else user
    password = settings.password if password is None else password
    if user:
        creds = f"{quote_plus(user)}:{quote_plus(password)}@"
        return (f"mongodb://{creds}{settings.host}:{settings.port}/"
                f"?authSource={settings.auth_db}&authMechanism=SCRAM-SHA-256")
    return f"mongodb://{settings.host}:{settings.port}/"


SETTINGS = Settings()