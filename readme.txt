Receptsamling – Recipe Library on Google Cloud Platform
=======================================================

This project provides a Python web application for collecting and managing
recipes. The UI allows you to upload new recipes (including an optional photo)
and remove existing ones. Recipes are persisted in Google Cloud Firestore and
any uploaded images are stored in Google Cloud Storage. The intended deployment
is a Google Compute Engine VM that exposes the Flask application via the
instance's external IP address.

Features
--------
- Upload recipes with a title, description, ingredients, instructions, and an
  optional image.
- View all stored recipes in a clean card-based layout.
- Remove unwanted recipes (also deleting associated Cloud Storage objects).
- Google Cloud native persistence with Firestore and Cloud Storage.

Architecture
------------
- **Flask** serves the UI, request handling, and validation.
- **Firestore** stores recipe metadata in a collection (defaults to
  ``recipes``).
- **Cloud Storage** keeps recipe images in a configured bucket under the
  ``recipes/`` prefix.

Environment configuration
-------------------------
The application relies on the following environment variables:

```
FLASK_SECRET_KEY    Secret used for Flask session cookies (default: development string).
GCP_PROJECT         Google Cloud project ID (required for production).
RECIPES_COLLECTION  Firestore collection name (defaults to "recipes").
GCS_BUCKET          Cloud Storage bucket used for storing recipe images.
GOOGLE_APPLICATION_CREDENTIALS  Path to a service account JSON key file with
                                Firestore and Storage permissions.
```

Firestore must be running in **Native mode**. Cloud Storage buckets must allow
the application service account to upload objects and expose images to end
users through signed URLs or IAM-based viewer access instead of calling
``make_public()``.

Local development
-----------------
1. Create and activate a virtual environment.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Export environment variables (use a service account JSON file downloaded
   from your GCP project).
4. Start the development server:
   ```
   flask --app main run --host=0.0.0.0 --port=8080
   ```

   Containers should instead rely on Gunicorn which is configured in the
   provided ``Dockerfile``.

Running on Compute Engine
-------------------------
1. Provision a VM (e.g., Debian/Ubuntu) with access to the required service
   account.
2. Install system packages (Python 3.10+, ``pip``).
3. Clone this repository onto the VM.
4. Install dependencies with ``pip install -r requirements.txt``.
5. Export the environment variables listed above (or provide them using
   ``systemd`` service files).
6. Start the application using ``gunicorn`` for production:
   ```
   gunicorn --bind 0.0.0.0:8080 main:app
   ```
7. Configure firewall rules to allow inbound traffic on the chosen port.

Testing
-------
Automated tests rely on an in-memory storage backend and do not require Google
Cloud access:
```
pytest
```

