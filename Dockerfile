# Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV DEFAULT_FONT_PATH=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
ENV UPLOAD_FOLDER=/app/uploads
ENV OUTPUT_FOLDER=/app/outputs
ENV MAX_CONTENT_LENGTH_MB=4096
ENV PORT=8000

COPY . .
RUN mkdir -p /app/uploads /app/outputs

EXPOSE 8000
CMD ["bash", "-lc", "gunicorn -w ${WEB_CONCURRENCY:-1} -b 0.0.0.0:${PORT:-8000} app:app"]
