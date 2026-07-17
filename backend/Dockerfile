FROM node:22-bookworm-slim AS node-runtime

FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        ca-certificates \
        chromium \
        chromium-driver \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && npm install -g @fly-ai/flyai-cli@1.0.16 \
    && npm cache clean --force

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
COPY backend/third_party/flights_monitor/requirements.txt \
    backend/third_party/flights_monitor/requirements.txt
RUN pip install \
    -r backend/requirements.txt \
    -r backend/third_party/flights_monitor/requirements.txt

COPY . .

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
