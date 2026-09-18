"""Run the development server: ``python -m tech2finder``."""

import os
from pathlib import Path

import uvicorn

from tech2finder.web.app import create_app

DEFAULT_STORE = Path(os.environ.get("TECH2FINDER_STORE", "data/tech2finder.db"))


def main() -> None:
    uvicorn.run(create_app(store_path=DEFAULT_STORE), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
