FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

# System deps for Pillow / bcrypt wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libjpeg62-turbo-dev \
       zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend /app/backend

EXPOSE 8000

RUN chmod +x /app/backend/entrypoint.sh

CMD ["/app/backend/entrypoint.sh"]
