# Dockerfile
FROM python:3.11-slim

# System deps (faster wheels, security)
RUN pip install --no-cache-dir --upgrade pip

# Create app dir and non-root user
WORKDIR /app
RUN useradd -m appuser

# Copy only files needed for pip first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
# Make sure your repo structure has:
# /app (package) with __init__.py, gcp_storage.py, models.py, storage.py
# /templates/*.html  and /static/*  (Flask will look here for render_template)
COPY . .

# Drop privileges
USER appuser

# Expose Flask/gunicorn port
EXPOSE 8080

# Start with gunicorn (prod)
CMD ["gunicorn", "-w", "2", "-k", "gthread", "-b", "0.0.0.0:8080", "--timeout", "120", "main:app"]
