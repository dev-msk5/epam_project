FROM python:3.13-slim

WORKDIR /app

#Upgrade pip only (setuptools/wheel come from pyproject.toml build-system)
RUN pip install --no-cache-dir --upgrade pip


# reads pyproject.toml and immediately looks for the src/ directory
COPY pyproject.toml .
COPY src/ src/

# Install all dependencies (cached layer - only reruns if pyproject.toml changes)
RUN pip install --no-cache-dir -e ".[dev]"

# Copy the rest of the project (code changes won't invalidate the pip layer)
COPY . .

# Security: don't run as root
RUN adduser --disabled-password --no-create-home appuser
USER appuser

RUN mkdir -p /app/logs

# Make sure app package is importable, NO SRC in imports
ENV PYTHONPATH=/app/src

# Don't buffer Python output, important for Docker logs
ENV PYTHONUNBUFFERED=1

# Don't write .pyc files into the container
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]