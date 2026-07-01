FROM python:3.13-slim

WORKDIR /app

# Upgrade pip only (setuptools/wheel come from pyproject.toml build-system)
RUN pip install --no-cache-dir --upgrade pip

# Reads pyproject.toml and immediately looks for the src/ directory
COPY pyproject.toml .
COPY src/ src/

# Install runtime dependencies only, dev tools (pytest/ruff/mypy) don't in prod
RUN pip install --no-cache-dir -e "."

# Copy the rest of the project (code changes won't invalidate the pip layer)
COPY . .

# Create logging dir and adjust permissions
RUN mkdir -p /app/logs

# Security: don't run as root, adjust directory ownership so appuser has access
RUN adduser --disabled-password --no-create-home appuser && \
    chown -R appuser:appuser /app

USER appuser

# Make sure app package is importable, NO SRC in imports
ENV PYTHONPATH=/app/src

# Don't buffer Python output, important for Docker logs
ENV PYTHONUNBUFFERED=1

# Don't write .pyc files into the container
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]