# OPTIONAL — see /Dockerfile's header comment. Streamlit dashboard
# container, built from the same repo (docker-compose.yml sets
# `context: .` with this as a secondary Dockerfile).

FROM python:3.11-slim

WORKDIR /app

COPY dashboard/requirements-dashboard.txt .
RUN pip install --no-cache-dir -r requirements-dashboard.txt

COPY dashboard/ ./dashboard/

WORKDIR /app/dashboard

EXPOSE 8501

CMD ["streamlit", "run", "Home.py", "--server.address=0.0.0.0"]
