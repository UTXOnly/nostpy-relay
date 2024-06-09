FROM python:3.11-slim

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        pkg-config \
        libc-dev \
        g++ \
        make \
    && rm -rf /var/lib/apt/lists/*
COPY ws_requirements.txt .
RUN pip install --no-cache-dir -r ws_requirements.txt

COPY ./websocket_handler.py .
COPY ./websocket_classes.py .


CMD [ "python", "websocket_handler.py"]