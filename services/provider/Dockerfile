# One image for every institution service; INSTITUTION_ID selects which institution an instance is.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY services/provider/requirements.txt /tmp/requirements.txt
COPY libs/common /libs/common
RUN pip install --no-cache-dir -r /tmp/requirements.txt /libs/common
COPY seed-data/patients /srv/seed-data/patients
COPY services/provider /srv
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
