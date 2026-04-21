from .web_server import run_web_app


def run_app(host="127.0.0.1", port=8000):
    run_web_app(host=host, port=port)
