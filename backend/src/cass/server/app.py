"""
CASS FastAPI Application
========================
Main entry point for the CASS API server.
"""

import json
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from fastapi.encoders import jsonable_encoder
from cass.server.auth import require_auth

from cass.integrations.database.postgres import PostgresRunner
from cass.integrations.llm.ollama import OllamaProvider
from cass.tools.run_sql import RunSQLTool
from cass.core.agent import Agent
from cass.core.llm import LlmMessage, Role

# Global instances (initialized on startup)
db: PostgresRunner | None = None
agent: Agent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown logic.

    - On startup: Connect to database, create agent
    - On shutdown: Close database connection
    """
    global db, agent

    # Startup
    print("Starting CASS...")

    # Connect to database
    db = PostgresRunner(os.environ.get("DATABASE_URL", "postgresql://postgres:casspass@localhost:5432/cassdb"))
    await db.connect()
    print("Database connected!")

    # Create LLM and tools
    llm = OllamaProvider(
        model=os.environ.get("OLLAMA_MODEL", "sqlcoder:7b"),
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
    )
    sql_tool = RunSQLTool(db)

    # Create agent
    agent = Agent(llm=llm, tools=[sql_tool])
    print("Agent ready!")

    try:
        yield
    finally:
        if db:
            await db.close()
        db = None
        agent = None


# Create the FastAPI app
app = FastAPI(
    title="CASS API",
    description="Conversational AI SQL System",
    version="0.1.0",
    dependencies=[Depends(require_auth)],
    lifespan=lifespan
)

# Allow frontend to connect (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CASS_ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "CASS is running!"}


@app.get("/schema")
async def get_schema():
    """Get the current database schema."""
    if db is None:
        raise HTTPException(503, "Database not connected")

    schema = await db.get_schema()
    return {"schema": schema}


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    answer: str
    sql: str | None = None
    data: list | None = None
    error: str | None = None  # Error message if SQL failed


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to CASS and get a response.
    Example:
        POST /chat
        {"message": "How many customers are there?"}
    """
    if agent is None or db is None:
        raise HTTPException(503, "System not initialized")

    # Get schema for context
    schema = await db.get_schema()

    # Get agent response
    response = await agent.chat(request.message, schema)

    return ChatResponse(
        answer=response.answer,
        sql=response.sql,
        data=response.data,
        error=response.error
    )


# =============================================================================
# Part 4: Additional Endpoints
# =============================================================================

@app.get("/tables")
async def list_tables():
    """List all tables in the database."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """
    tables = await db.execute(query)
    return {"tables": [t["table_name"] for t in tables]}


@app.get("/tables/{table_name}")
async def describe_table(table_name: str):
    """Get detailed information about a specific table."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    columns = await db.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
    """, table_name)

    if not columns:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    # Get row count
    quoted = '"' + table_name.replace('"', '""') + '"'
    count_result = await db.execute(f"SELECT COUNT(*) as count FROM public.{quoted}")
    row_count = count_result[0]["count"] if count_result else 0

    return {
        "table": table_name,
        "columns": columns,
        "row_count": row_count
    }


class SqlRequest(BaseModel):
    """Request body for raw SQL execution."""
    sql: str = Field(min_length=1, max_length=20000)


@app.post("/sql")
async def execute_sql(request: SqlRequest):
    """
    Execute raw SQL query (SELECT only for safety).

    Example:
        POST /sql
        {"sql": "SELECT * FROM customers LIMIT 5"}
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    try:
        results = await db.execute(request.sql)
        return {"data": results, "row_count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/sample/{table_name}")
async def get_sample_data(table_name: str, limit: int = Query(default=5, ge=1, le=500)):
    """Get sample rows from a table."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    try:
        quoted = '"' + table_name.replace('"', '""') + '"'
        results = await db.execute(f"SELECT * FROM public.{quoted} LIMIT $1", limit)
        return {"table": table_name, "data": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Part 3: Streaming Endpoint (SSE)
# =============================================================================

async def stream_chat_response(message: str, schema: str) -> AsyncGenerator[str, None]:
    """Generate SSE events for streaming chat response."""
    if agent is None:
        yield f"data: {json.dumps({'type': 'error', 'content': 'Agent not ready'})}\n\n"
        return

    # Send start event
    yield f"data: {json.dumps({'type': 'start', 'content': ''})}\n\n"

    # Get the agent's LLM for streaming
    messages = [
        LlmMessage(role=Role.SYSTEM, content=agent.system_prompt),
        LlmMessage(role=Role.SYSTEM, content=f"DATABASE SCHEMA:\n{schema}"),
        LlmMessage(role=Role.USER, content=message)
    ]

    full_response = ""

    try:
        # Stream tokens (type: ignore for async generator typing issue)
        async for token in agent.llm.chat_stream(messages):  # type: ignore
            full_response += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        # Extract SQL from full response
        sql = agent._extract_sql(full_response)

        if sql:
            yield f"data: {json.dumps({'type': 'sql', 'content': sql})}\n\n"

            # Execute SQL
            if db is not None:
                result = await agent.tools["run_sql"].execute(sql=sql)
                if result.success:
                    yield f"data: {json.dumps(jsonable_encoder({'type': 'data', 'content': result.data}))}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'content': result.error})}\n\n"

        # Send end event
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    yield f"data: {json.dumps({'type': 'end', 'content': ''})}\n\n"


@app.post("/chat/stream")
async def chat_stream_post(request: ChatRequest):
    return await chat_stream(request.message)


@app.get("/chat/stream")
async def chat_stream(message: str = Query(min_length=1, max_length=4000)):
    """
    Stream chat response using Server-Sent Events (SSE).

    Example:
        GET /chat/stream?message=How%20many%20customers%20are%20there

    Events:
        - start: Stream started
        - token: Individual token from LLM
        - sql: Extracted SQL query
        - data: Query results
        - error: Error message
        - end: Stream complete
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    schema = await db.get_schema()

    return StreamingResponse(
        stream_chat_response(message, schema),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
