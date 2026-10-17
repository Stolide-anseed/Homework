import json
from pathlib import Path

from locust import HttpUser, between, task

DATA_PATH = Path(__file__).resolve().parent / "test.json"
FEATURES = json.loads(DATA_PATH.read_text(encoding="utf-8"))


class MobilePriceUser(HttpUser):
    wait_time = between(0.1, 0.3)

    @task
    def predict(self):
        with self.client.post(
            "/v1/predict",
            json=FEATURES,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return

            try:
                price = response.json()["mobile_price"]
                if type(price) not in (int, float) or price not in (0, 1, 2, 3):
                    response.failure("Недопустимое предсказание")
            except (ValueError, KeyError, TypeError):
                response.failure("Некорректный JSON-ответ")