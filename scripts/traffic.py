"""Трафик к Mobile Price через Ingress для дашборда Grafana.

  uv run python scripts/traffic.py --url http://mobile.localhost --rps 5 --bad 0.05

--bad: доля запросов без обязательного признака ram (HTTP 422).
Для проверки rollout без ошибок используйте --bad 0. Остановка: Ctrl+C.
"""
import argparse
import json
import random
import time
import urllib.error
import urllib.request

import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://mobile.localhost")
parser.add_argument("--rps", type=float, default=5)
parser.add_argument("--bad", type=float, default=0.0)
args = parser.parse_args()

df = pd.read_csv("data/train.csv").drop(columns=["price_range"])
rows = df.to_dict("records")

codes: dict[int, int] = {}
start = time.time()
try:
    while True:
        row = dict(random.choice(rows))
        if random.random() < args.bad:
            row.pop("ram")
        req = urllib.request.Request(
            f"{args.url}/v1/predict",
            data=json.dumps(row).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                code = resp.status
        except urllib.error.HTTPError as e:
            code = e.code
            e.close()
        except (urllib.error.URLError, OSError):
            code = 0  # Сервис недоступен или соединение оборвалось.
        codes[code] = codes.get(code, 0) + 1
        total = sum(codes.values())
        if total % 50 == 0:
            print(f"{total} запросов за {time.time() - start:.0f} с, коды {codes}", flush=True)
        time.sleep(1 / args.rps)
except KeyboardInterrupt:
    print(f"Итого: {sum(codes.values())} запросов, коды {codes}", flush=True)
