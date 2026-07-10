FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

WORKDIR /app
COPY . /app
RUN mkdir -p /data && useradd --create-home --uid 10001 botuser && chown -R botuser:botuser /app /data
USER botuser

CMD ["python", "bot.py"]

