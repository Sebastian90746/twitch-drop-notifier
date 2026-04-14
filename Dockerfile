FROM python:3.12-slim

WORKDIR /app

# Dependencies installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-Code kopieren
COPY app/ .

# Datenverzeichnis für State
VOLUME ["/data", "/config"]

CMD ["python", "main.py"]
