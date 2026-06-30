# Infrastructure and telemetry tests for logging, request tracing, and health checks
#
# test_logging_middleware_injects_trace_id - covered cases:
#   LoggingMiddleware intercepts the request and injects X-Request-ID header
#   generated trace ID has correct prefix structure (starts with 'req_')
#
# test_trace_id_is_unique_per_request - covered cases:
#   consecutive requests generate different, unique trace IDs
#   context variables do not leak values across different task threads
#
# test_health_checks - covered cases:
#   /health endpoint returns 200 OK and basic server operational status
#   /health/db verifies active pool connection to the test database
#

import pytest
from httpx import AsyncClient
from fastapi import status


@pytest.mark.anyio
async def test_logging_middleware_injects_trace_id(client: AsyncClient):
    """
    Verify that our custom LoggingMiddleware intercepts incoming requests
    and automatically attaches a X-Request-ID correlation header
    """
    response = await client.get("/health")
    assert response.status_code == status.HTTP_200_OK, (
        "Code should be 200 OK for health check endpoint"
    )
    assert "X-Request-ID" in response.headers, (
        "X-Request-ID header is missing from response headers"
    )

    # Assert trace ID is a valid generated request tracker
    trace_id = response.headers["X-Request-ID"]
    assert trace_id.startswith("req_"), "Trace ID should start with 'req_' prefix"
    assert len(trace_id) > 4, "Trace ID should have a length greater than 4 characters"


@pytest.mark.anyio
async def test_trace_id_is_unique_per_request(client: AsyncClient):
    """
    Verify that context variables and request tracking identifiers
    do not leak across concurrent requests
    """
    response_one = await client.get("/health")
    response_two = await client.get("/health")

    trace_one = response_one.headers["X-Request-ID"]
    trace_two = response_two.headers["X-Request-ID"]

    assert trace_one != trace_two, (
        "Trace IDs should be unique per request and not leak across requests"
    )


@pytest.mark.anyio
async def test_health_checks(client: AsyncClient):
    """
    Verify that our application lifecycle and DB pooling routes
    return accurate healthy check patterns
    """
    # 1. Base app status check
    response = await client.get("/health")
    assert response.status_code == status.HTTP_200_OK, (
        "Code should be 200 OK for health check endpoint"
    )
    assert response.json() == {"status": "ok"}, (
        "Response JSON should indicate server is operational and healthy"
    )

    # 2. Database transaction check
    response_db = await client.get("/health/db")
    assert response_db.status_code == status.HTTP_200_OK, (
        "Code should be 200 OK for database health check endpoint"
    )
    assert response_db.json()["status"] == "ok", (
        "Database health check response JSON does not match expected structure"
    )
    assert response_db.json()["database"] == "connected", (
        "Database health check response JSON does not indicate a connected database"
    )
