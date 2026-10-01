FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY services/clinic/requirements.txt /tmp/requirements.txt
COPY libs/common /libs/common
RUN pip install --no-cache-dir -r /tmp/requirements.txt /libs/common
COPY services/clinic /srv
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
