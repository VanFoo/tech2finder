"""The FastAPI application.

Views stay thin on purpose: each builds a plain dataclass and hands it to a
template. Domain arithmetic lives behind that boundary (ADR-0012).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from tech2finder.store.bootstrap import bootstrap
from tech2finder.web.status import store_status

TEMPLATES = Path(__file__).parent / "templates"


def create_app(store_path: Path) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Once, at startup. Views are sync, so FastAPI dispatches them to a
        # threadpool and several run at once; migrating from a request handler
        # would race two callers into applying the same migration twice.
        bootstrap(store_path)
        yield

    app = FastAPI(title="tech2finder", lifespan=lifespan)
    templates = Jinja2Templates(directory=TEMPLATES)

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="status.html",
            context={"status": store_status(store_path)},
        )

    return app
