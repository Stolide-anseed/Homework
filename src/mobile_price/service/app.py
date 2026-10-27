import logging
import time
import uuid
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from mobile_price import db
from mobile_price.config import settings
from mobile_price.model_store import load_model

PREDICTIONS = Counter(
    "mobile_price_predictions_total",
    "Predictions by price class",
    ["price_class"],
)

MODEL_INFO = Gauge(
    "mobile_price_model_info",
    "Model loaded by this pod",
    ["version"],
)
# в среднем ответы занимают около 16ms
LATENCY_BUCKETS = (
    0.002, 0.005, 0.01, 0.015, 0.02,
    0.025, 0.05, 0.1, 0.25, 0.5, 1,
)

logger = logging.getLogger(__name__)


class Features(BaseModel):
    model_config = {'extra':'forbid'}

    battery_power: int
    blue: int
    clock_speed:float
    dual_sim: int
    fc: int
    four_g: int
    int_memory:int
    m_dep: float
    mobile_wt: int
    n_cores: int
    pc:int
    px_height: int
    px_width: int
    ram: int
    sc_h: int
    sc_w: int
    talk_time: int
    three_g: int
    touch_screen: int
    wifi:int


class Prediction(BaseModel):

    mobile_price: float
    model_version:str
    request_id: str
    latency_ms: float
    status_code: int

class BatchFeatures(BaseModel):
    rows: list[Features] = Field(max_length=1000, min_length=1)

class BatchPrediction(BaseModel):

    mobile_price: list[float]
    model_version:str
    request_id: str
    latency_ms: float
    status_code: int

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pipeline, app.state.meta, app.state.version = load_model()
    MODEL_INFO.labels(app.state.version).set(1)
    
    db.init()
    yield
    app.state.pipeline = None

app = FastAPI(title="Mobile Price Prediction API", version="1.0", lifespan=lifespan)
Instrumentator().instrument(app, latency_lowr_buckets=LATENCY_BUCKETS).expose(app)


# для отлавливания ошибки до предикта
@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.started_at = time.perf_counter()
    request.state.request_id = str(uuid.uuid4())
    request.state.features = {}

    return await call_next(request)


# для сохранения ошибки
def save_error(request: Request, features: dict, status_code: int):
    latency_ms = (
        time.perf_counter() - request.state.started_at
    ) * 1000

    try:
        db.save_prediction(
            request_id=request.state.request_id,
            features=features,
            mobile_price=None,
            model_version=getattr(app.state, "version", "unknown"),
            latency_ms=latency_ms,
            status_code=status_code,
        )
    except Exception:
        logger.exception("Не удалось записать ошибочный запрос в базу")


# обработчик 422
@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
):
    response = await request_validation_exception_handler(request, exc)

    response.headers["X-Request-ID"] = request.state.request_id

    if request.url.path == "/v1/predict":
        features = (
            exc.body
            if isinstance(exc.body, dict)
            else {"raw_body": str(exc.body)}
        )

        response.background = BackgroundTask(
            save_error, request, features, 422
        )

    return response



@app.get('/health')
def health():
    return {'status': 'ok', 'model_version': app.state.version, 'service_version': '1.2', 'path': settings.model_path}

@app.get('/ready')
def ready():
    if getattr(app.state, 'pipeline', None) is None:
        raise HTTPException(status_code=503, detail="Pipeline not loaded")

    return {'status': 'ok'}


@app.post('/v1/predict')
def predict(x: Features, bg: BackgroundTasks, request: Request):
    t0 = time.perf_counter()
    request_id = request.state.request_id
    payload = x.model_dump()

    request.state.features = payload

    frame = pd.DataFrame([payload]).reindex(columns=app.state.meta['features'])

    mobile_price = float(app.state.pipeline.predict(frame)[0])

    latency_ms = (time.perf_counter() - t0) * 1000

    # 200, так как добавляются только успешно сработанные запросы
    status_code = 200

    bg.add_task(
        db.save_prediction,
        request_id=request_id,
        features = payload,
        mobile_price = mobile_price,
        model_version = app.state.version,
        latency_ms = latency_ms,
        status_code = status_code
    )

    PREDICTIONS.labels(price_class=str(int(mobile_price))).inc()
    
    return (
            Prediction(
                mobile_price=mobile_price,
                model_version = app.state.version,
                request_id=request_id,
                latency_ms=latency_ms,
                status_code = status_code)
        )

# для по батчевого предсказания
@app.post('/v1/predict/batch')
def predict_batch(X : BatchFeatures, bg: BackgroundTasks):
    t0 = time.perf_counter()

    request_id = str(uuid.uuid4())
    frame = pd.DataFrame([row.model_dump() for row in X.rows]).reindex(columns=app.state.meta['features'])

    mobile_prices = app.state.pipeline.predict(frame).tolist()

    latency_ms = (time.perf_counter() - t0) * 1000

    # 200, так как добавляются только успешно сработанные запросы
    status_code = 200

    # По хорошему нужно сделать отдельную функцию для того, чтобы n-ое кол-во раз не взаимодействовать с базой

    for price, x in zip(mobile_prices, X.rows, strict=True):
        bg.add_task(
            db.save_prediction,
            request_id=request_id,
            features = x.model_dump(),
            mobile_price = price,
            model_version = app.state.version,
            latency_ms = latency_ms,
            status_code = status_code)


    return (
        BatchPrediction(
            mobile_price=mobile_prices,
            model_version = app.state.version,
            request_id=request_id,
            latency_ms=latency_ms,
            status_code = status_code
        )
    )
