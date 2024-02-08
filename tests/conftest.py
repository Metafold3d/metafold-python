from http.server import ThreadingHTTPServer
from metafold import MetafoldClient
import pytest
import threading


@pytest.fixture(scope="module", autouse=True)
def api(request_handler):
    with ThreadingHTTPServer(("localhost", 8000), request_handler) as httpd:
        # Start test HTTP server in a separate thread
        thread = threading.Thread(target=httpd.serve_forever)
        thread.daemon = True
        thread.start()
        yield
        httpd.shutdown()


@pytest.fixture(scope="session")
def client():
    return MetafoldClient("testtoken", "1", base_url="http://localhost:8000")
