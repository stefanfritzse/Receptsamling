"""WSGI entrypoint for the Receptsamling application.

The Flask development server is intentionally not started from this module so
that containerized deployments rely on Gunicorn (see ``Dockerfile``). Local
development can still use ``flask --app main run`` which imports the ``app``
object defined below.
"""

from app import create_app

app = create_app()


__all__ = ["app"]
