# Ticket d'incident 3

> **Statut : ✅ corrigé le 07/10/2026** (pull request n° 1, merged into `ticket3` from `fix/ticket3-corrections`)

## Étapes pour reproduire le problème
1. Lancer l'application.
2. Sélectionner *Voir les prédictions*.
3. La *liste des prédictions enregistrées* n'affiche que des *prédiction None*.

## Résultat actuel
Toutes les *prédictions* sont nommées *none*.

![Capture d'écran de l'incident](./ressources/ticket3.png)

## Comportement attendu
Les prédictions doivent être numérotées dans la *liste des prédictions enregistrées*.

## Résolution

### Incident
La liste des prédictions affichait « None » à la place du numéro de chaque prédiction :
l'API renvoyait `"id": null` sur `GET /predictions/`.

### Cause
La requête SQL de `lister_predictions()` (`api/app/bdd/service.py`) ne sélectionnait pas la colonne
`predictions.id`. Le modèle Pydantic `Prediction` déclare `id: int | None = None`, donc l'absence de la clé donnait `id = None`, sans aucune erreur levée.

### Correction
Ajout de `predictions.id as id` dans le `SELECT` de `lister_predictions()` (une ligne modifiée dans `service.py`).

### Validation
- Débogueur : `rows[0].keys()` ne contenait pas `id` avant la correction.
- Écriture correcte : le `POST /predictions/satellite/` renvoyait un `id`.
- Tests unitaires : échec avant la correction (`docs/pytest_avant.txt`), succès après (`docs/pytest_apres.txt`).
- `GET /predictions/` renvoie maintenant des `id` numériques.

### Hors périmètre
Anomalies observées pendant le diagnostic, non corrigées dans ce ticket :
- Après l'ajout d'une nouvelle image, la dernière prédiction de la liste n'apparaît pas
  (cause probable : `rows[:length]` avec `length = len(rows) - 1` dans `lister_predictions()` constaté à la lecture du code et tests sur Swagger).
- Chemin d'image absolu supérieur à 100 caractères en local : erreur MySQL 1406
  (colonne `image` en `varchar(100)`), contournée localement avec un chemin d'upload court.

---

## Monitoring

```
API FastAPI (/metrics) → Prometheus → Grafana (tableau de bord)
                              ↓
                        Alertmanager → e-mail (SMTP) → Mailpit
```

| Outil | Adresse |
|---|---|
| Métriques de l'API | http://localhost:8081/metrics |
| Prometheus (règles, alertes) | http://localhost:9090 |
| Grafana (tableau de bord) | http://localhost:3000 |
| Alertmanager (envoi des e-mails d'alerte) | http://localhost:9093 |
| Mailpit (e-mails de notification reçus) | http://localhost:8025 |


**Démarrage :** créer un fichier `.env` à la racine, puis lancer `docker compose up --build -d`.
Huit conteneurs démarrent : l'application (base MySQL, Adminer, API FastAPI, client Streamlit)
et les outils de monitoring (Prometheus, Grafana, Alertmanager, Mailpit).

- Configuration versionnée dans `monitoring/` : `prometheus.yml`, `alert_rules.yml`, `alertmanager.yml` et la configuration de Grafana (source de données et tableau de bord).
- Notifications : Alertmanager envoie un e-mail quand une alerte se déclenche (`[FIRING]`). En local, Mailpit sert de serveur SMTP de test.
- Alerte testée le 19/11/2026 : l'arrêt du service `web` fait passer `ApiIndisponible` en Firing, et un e-mail est reçu dans Mailpit.