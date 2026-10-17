"""Browser-only infrastructure: real composition/routes/CORS, fake persistence.

No fixtures are imported into the production frontend or written to a database.
"""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
os.environ["CORS_ALLOWED_ORIGINS"] = "http://127.0.0.1:4321"

from application.lockers.ports import LockerRepository
from main import create_app

repository = AsyncMock(spec=LockerRepository)
repository.list_all.return_value = []
with (
    patch("main.create_database", return_value=(AsyncMock(), object())),
    patch("main.SqlModelLockerRepository", return_value=repository),
):
    app = create_app("postgresql+asyncpg://unused/unused", publisher=AsyncMock())

uvicorn.run(app, host="127.0.0.1", port=8765)
