"""Frontend registry. v0.1 ships the Python frontend only."""

from .python_frontend import PythonFrontend

FRONTENDS = {"python": PythonFrontend}
