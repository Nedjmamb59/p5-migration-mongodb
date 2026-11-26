"""Préparations partagées par tous les tests (les "fixtures")."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # permet d'écrire "from app ..." dans les tests

from app.config import SETTINGS  # noqa: E402
from app.transform import clean_dataframe, load_csv  # noqa: E402


@pytest.fixture(scope="session")
def raw_df():
    """Le CSV tel que livré par le client."""
    return load_csv(os.getenv("CSV_PATH", str(ROOT / "data" / "healthcare_dataset.csv")))


@pytest.fixture(scope="session")
def clean_df(raw_df):
    """Le CSV après nettoyage."""
    return clean_dataframe(raw_df)


def _client_or_skip(user, password):
    """Se connecte à MongoDB, ou met le test de côté si la base est injoignable."""
    from app.database import get_client
    try:
        return get_client(user=user, password=password, retries=1, delay=0)
    except ConnectionError as exc:
        pytest.skip(f"MongoDB non disponible : {exc}")


@pytest.fixture(scope="session")
def collection():
    """La collection migrée, lue avec le compte de migration."""
    client = _client_or_skip(SETTINGS.user, SETTINGS.password)
    yield client[SETTINGS.database][SETTINGS.collection]
    client.close()


@pytest.fixture(scope="session")
def role_client():
    """Fabrique des connexions avec un compte donné, pour tester les rôles."""
    clients = []

    def _make(user_var, password_var):
        user, password = os.getenv(user_var), os.getenv(password_var)
        if not user:
            pytest.skip(f"{user_var} non défini")
        client = _client_or_skip(user, password)
        clients.append(client)
        return client[SETTINGS.database][SETTINGS.collection]

    yield _make
    for c in clients:
        c.close()