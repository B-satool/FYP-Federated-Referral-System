# Central API and background worker share this image (different commands).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY services/central/requirements.txt /tmp/requirements.txt
COPY libs/common /libs/common
RUN pip install --no-cache-dir -r /tmp/requirements.txt /libs/common
COPY rules /srv/assets/rules
COPY seed-data/patients /srv/assets/seed-data/patients
COPY services/central /srv
ENV REPO_ASSETS=/srv/assets
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
