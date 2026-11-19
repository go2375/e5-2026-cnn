from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
import logging
import shutil
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from mysql.connector import Error as DatabaseError
from PIL import Image, UnidentifiedImageError
from app.modele import cnn
from app.config import UPLOAD_FOLDER
from app.bdd.service import Service_Prediction
from app.bdd.prediction import Prediction
import time
from fastapi import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

REQUESTS_TOTAL = Counter(
    "api_requests_total",
    "Nombre de requetes HTTP",
    ["route", "method", "code"],
)

INFERENCE_SECONDS = Histogram(
    "prediction_inference_seconds",
    "Duree de l'inference du modele",
)

CLASS_TOTAL = Counter(
    "prediction_class_total",
    "Nombre de predictions par classe",
    ["label"],
)

PREDICTION_ID_MISSING_TOTAL = Counter(
    "prediction_id_missing_total",
    "Nombre de predictions recuperees sans identifiant",
)

@asynccontextmanager
async def lifespan(app):
    Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
    cnn.get_model()
    yield


app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    response = await call_next(request)

    if request.url.path != "/metrics":
        REQUESTS_TOTAL.labels(
            route=request.url.path,
            method=request.method,
            code=str(response.status_code),
        ).inc()

    return response

@app.exception_handler(DatabaseError)
async def database_error(request: Request, exc: DatabaseError):
    logging.getLogger(__name__).error("Erreur MySQL : %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Base de données indisponible"})


@app.get("/")
def index():
    return "API Prediction!"

@app.post("/predictions/satellite/")
def upload_image(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        file.file.close()
        raise HTTPException(status_code=400, detail="Format non supporté")
    file_path = Path(UPLOAD_FOLDER) / f"{uuid4().hex}{suffix}"
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        try:
            with Image.open(file_path) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise HTTPException(status_code=400, detail="Image invalide") from exc
        start_time = time.perf_counter()

        label = cnn.predict_image(file_path)

        INFERENCE_SECONDS.observe(time.perf_counter() - start_time)

        CLASS_TOTAL.labels(label=label).inc()

        log.info("Inference terminee : label=%s", label)
        prediction = Prediction(image=str(file_path), label=label, commentaire="OK", modele="CNN")
        Service_Prediction.sauvegarder_prediction(prediction)
        log.info("Prediction enregistree via l'API : id=%s", prediction.id)
        return {"prediction": prediction}
    except Exception:
        file_path.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()


@app.get("/predictions/", response_model=list[Prediction])
def list_predictions():
    predictions = Service_Prediction.lister_predictions()

    missing_ids = sum(
        1 for prediction in predictions
        if prediction.id is None
    )

    if missing_ids > 0:
        PREDICTION_ID_MISSING_TOTAL.inc(missing_ids)

        log.error(
            "Predictions recuperees sans ID : %s",
            missing_ids,
        )

    return predictions

@app.get("/metrics") 
def metrics(): 

    return Response( 
        content=generate_latest(), 
        media_type=CONTENT_TYPE_LATEST, 
    )