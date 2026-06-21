FROM python:3.13-slim

WORKDIR /app

# Step 1: Install build tools first
RUN pip install --upgrade pip setuptools wheel

# Step 2: Copy and install project dependencies
COPY pyproject.toml .
RUN pip install -e ".[dev]"

# Step 3: Copy source code
COPY . .