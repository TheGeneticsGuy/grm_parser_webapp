# Dockerfile

FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000

# The command to run the application when the container starts
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8000", "--timeout", "300", "wsgi:application"]