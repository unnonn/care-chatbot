FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HABIT_DB_PATH=/data/habits.db \
    TZ=Asia/Tokyo

WORKDIR /app

# Build context is the habit_tracker/ directory itself (fly deploy from inside it)
COPY requirements.txt /app/habit_tracker/requirements.txt
RUN pip install --no-cache-dir -r /app/habit_tracker/requirements.txt

COPY . /app/habit_tracker

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080

CMD ["sh", "-c", "uvicorn habit_tracker.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
