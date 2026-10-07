from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from app.bdd.prediction import Prediction
from app.bdd.service import Service_Prediction


def faux_cursor(rows):
    """Cursor MySQL simulé : renvoie `rows` à fetchall()."""
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    return cursor


def brancher(monkeypatch, cursor):
    """Remplace la connexion MySQL par un faux contexte."""
    @contextmanager
    def faux_ouvrir():
        yield MagicMock(), cursor

    monkeypatch.setattr(
        Service_Prediction, "ouvrir_connexion", staticmethod(faux_ouvrir)
    )


ROWS = [
    {"id": 1, "image": "a.jpg", "label": "forêt", "commentaire": "OK", "modele": "CNN"},
    {"id": 2, "image": "b.jpg", "label": "mer", "commentaire": "OK", "modele": "CNN"},
    {"id": 3, "image": "c.jpg", "label": "désert", "commentaire": "OK", "modele": "CNN"},
]


# Test 1 : la requête de lecture sélectionne l'id (cause du ticket 3)
def test_requete_liste_selectionne_id(monkeypatch):
    cursor = faux_cursor([])
    brancher(monkeypatch, cursor)

    Service_Prediction.lister_predictions()

    sql = " ".join(cursor.execute.call_args[0][0].lower().split())
    assert "predictions.id as id" in sql


# Test 2 : les prédictions renvoyées ont un id numérique, jamais None
def test_liste_renvoie_des_id_numeriques(monkeypatch):
    brancher(monkeypatch, faux_cursor([dict(r) for r in ROWS]))

    resultat = Service_Prediction.lister_predictions()

    assert len(resultat) > 0
    assert all(isinstance(p.id, int) for p in resultat)
    assert [p.id for p in resultat][:2] == [1, 2]


# Test 3 : non-régression du modèle Pydantic (sans id, il reste None)
def test_prediction_sans_id_reste_none():
    p = Prediction(image="a.jpg", label="forêt", commentaire="OK", modele="CNN")
    assert p.id is None
