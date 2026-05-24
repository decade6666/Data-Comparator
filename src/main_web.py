import os

import uvicorn

WEB_HOST_ENV = "DATASET_COMPARATOR_WEB_HOST"
WEB_PORT_ENV = "DATASET_COMPARATOR_WEB_PORT"
DEFAULT_WEB_HOST = "0.0.0.0"
DEFAULT_WEB_PORT = 8000


def _get_web_port() -> int:
    port_text = os.environ.get(WEB_PORT_ENV, str(DEFAULT_WEB_PORT))
    try:
        return int(port_text)
    except ValueError as exc:
        raise ValueError(f"{WEB_PORT_ENV} 必须是整数") from exc


def main() -> None:
    uvicorn.run(
        "src.frontend.web_api:app",
        host=os.environ.get(WEB_HOST_ENV, DEFAULT_WEB_HOST),
        port=_get_web_port(),
    )


if __name__ == "__main__":
    main()
