FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 app \
    && useradd --create-home --uid 10001 --gid 10001 app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=10001:10001 . .

# Seed the named-volume mount points so a new volume gets app-owned content.
RUN install -d -o 10001 -g 10001 /data /app/staticfiles /app/media \
    && touch /data/.volume-seed \
             /app/staticfiles/.volume-seed \
             /app/media/.volume-seed \
    && chown -R 10001:10001 /data /app/staticfiles /app/media

USER app
