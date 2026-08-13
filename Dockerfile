# Holy Month AI — backend container.
#
# OPTIONAL. Local Windows/Mac/Linux use via `python holy_month_automation.py
# web` (see README.md) needs no Docker at all — this exists for anyone who
# wants to deploy the backend on a Linux host/VPS instead of running it
# directly. The dashboard is a separate container (see docker-compose.yml)
# since it's a different process with different, lighter dependencies.

FROM python:3.11-slim

# ffmpeg is a hard requirement (video assembly) — not available via pip.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY holy_month/ ./holy_month/
COPY holy_month_automation.py .

# .env, holy_month.db, output_videos/, logs/, backups/ are all meant to be
# mounted as volumes (see docker-compose.yml) — NOT baked into the image,
# so secrets never end up in an image layer and data survives a rebuild.

EXPOSE 8000

CMD ["python", "holy_month_automation.py", "web"]
