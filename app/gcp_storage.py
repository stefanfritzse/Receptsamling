from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import Iterable, List, Optional

from google.api_core import exceptions as gcloud_exceptions
from google.auth import exceptions as auth_exceptions
from google.cloud import firestore, storage
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .models import Recipe
from .storage import RecipeRepository


SIGNED_URL_EXPIRATION = timedelta(days=7)


def _parse_ingredients(ingredients_text: str) -> List[str]:
    return [line.strip() for line in ingredients_text.splitlines() if line.strip()]


class FirestoreRecipeStorage(RecipeRepository):
    """GCP backed recipe storage using Firestore and Cloud Storage."""

    def __init__(
        self,
        *,
        project: Optional[str] = None,
        collection_name: str = "recipes",
        bucket_name: Optional[str] = None,
    ) -> None:
        self._project = project
        self._collection_name = collection_name
        self._bucket_name = bucket_name

        self._firestore_client = firestore.Client(project=project)
        self._collection = self._firestore_client.collection(collection_name)

        if bucket_name:
            self._storage_client = storage.Client(project=project)
            self._bucket = self._storage_client.bucket(bucket_name)
        else:
            self._storage_client = None
            self._bucket = None

    @classmethod
    def from_env(cls) -> "FirestoreRecipeStorage":
        """Build a storage instance from environment variables."""

        project = os.environ.get("GCP_PROJECT")
        collection_name = os.environ.get("RECIPES_COLLECTION", "recipes")
        bucket_name = os.environ.get("GCS_BUCKET")
        return cls(project=project, collection_name=collection_name, bucket_name=bucket_name)

    def list_recipes(self) -> Iterable[Recipe]:
        query = self._collection.order_by("created_at", direction=firestore.Query.DESCENDING)
        docs = query.stream()
        for doc in docs:
            data = doc.to_dict() or {}
            yield self._doc_to_recipe(doc.id, data)

    def get_recipe(self, recipe_id: str) -> Recipe:
        doc_ref = self._collection.document(recipe_id)
        snapshot = doc_ref.get()

        if not snapshot.exists:
            raise KeyError(f"Recipe '{recipe_id}' does not exist.")

        data = snapshot.to_dict() or {}
        return self._doc_to_recipe(snapshot.id, data)

    def add_recipe(
        self,
        *,
        title: str,
        description: str,
        ingredients_text: str,
        instructions: str,
        image: FileStorage | None,
    ) -> Recipe:
        ingredients = _parse_ingredients(ingredients_text)

        image_url: Optional[str] = None
        blob_name: Optional[str] = None

        if image and image.filename:
            if not self._bucket:
                raise RuntimeError("A Cloud Storage bucket must be configured to upload images.")

            blob_name = self._build_blob_name(image.filename)
            blob = self._bucket.blob(blob_name)

            image.stream.seek(0)
            blob.upload_from_file(image.stream, content_type=image.mimetype)
            image_url = self._get_image_url(blob)

        doc = {
            "title": title,
            "description": description,
            "ingredients": ingredients,
            "instructions": instructions,
            "image_url": image_url,
            "image_blob_name": blob_name,
            "created_at": firestore.SERVER_TIMESTAMP,
        }

        doc_ref = self._collection.document()
        doc_ref.set(doc)

        snapshot = doc_ref.get()
        data = snapshot.to_dict() or {}
        return self._doc_to_recipe(snapshot.id, data)

    def delete_recipe(self, recipe_id: str) -> None:
        doc_ref = self._collection.document(recipe_id)
        snapshot = doc_ref.get()

        if not snapshot.exists:
            raise KeyError(f"Recipe '{recipe_id}' does not exist.")

        data = snapshot.to_dict() or {}
        blob_name = data.get("image_blob_name")

        self._delete_blob_if_exists(blob_name)

        doc_ref.delete()

    def update_recipe(
        self,
        recipe_id: str,
        *,
        title: str,
        description: str,
        ingredients_text: str,
        instructions: str,
        image: FileStorage | None,
        remove_image: bool = False,
    ) -> Recipe:
        doc_ref = self._collection.document(recipe_id)
        snapshot = doc_ref.get()

        if not snapshot.exists:
            raise KeyError(f"Recipe '{recipe_id}' does not exist.")

        current_data = snapshot.to_dict() or {}
        current_blob_name = current_data.get("image_blob_name")
        current_image_url = current_data.get("image_url")

        ingredients = _parse_ingredients(ingredients_text)

        new_blob_name = current_blob_name
        new_image_url = current_image_url

        if image and image.filename:
            if not self._bucket:
                raise RuntimeError("A Cloud Storage bucket must be configured to upload images.")

            if current_blob_name:
                self._delete_blob_if_exists(current_blob_name)

            new_blob_name = self._build_blob_name(image.filename)
            blob = self._bucket.blob(new_blob_name)

            image.stream.seek(0)
            blob.upload_from_file(image.stream, content_type=image.mimetype)
            new_image_url = self._get_image_url(blob)
        elif remove_image:
            self._delete_blob_if_exists(current_blob_name)
            new_blob_name = None
            new_image_url = None

        update_doc = {
            "title": title,
            "description": description,
            "ingredients": ingredients,
            "instructions": instructions,
            "image_blob_name": new_blob_name,
            "image_url": new_image_url,
        }

        doc_ref.update(update_doc)

        snapshot = doc_ref.get()
        data = snapshot.to_dict() or {}
        return self._doc_to_recipe(snapshot.id, data)

    def _doc_to_recipe(self, doc_id: str, data: dict) -> Recipe:
        ingredients = data.get("ingredients")
        if isinstance(ingredients, str):
            parsed_ingredients = _parse_ingredients(ingredients)
        elif isinstance(ingredients, list):
            parsed_ingredients = ingredients
        else:
            parsed_ingredients = []

        created_at = data.get("created_at")
        if isinstance(created_at, datetime):
            timestamp = created_at
        else:
            timestamp = None

        image_blob_name = data.get("image_blob_name")
        image_url = data.get("image_url")

        if image_blob_name and self._bucket:
            blob = self._bucket.blob(image_blob_name)
            image_url = self._get_image_url(blob)

        return Recipe(
            id=doc_id,
            title=data.get("title", ""),
            description=data.get("description", ""),
            ingredients=parsed_ingredients,
            instructions=data.get("instructions", ""),
            image_url=image_url,
            created_at=timestamp,
        )

    def _build_blob_name(self, filename: str) -> str:
        safe = secure_filename(filename)
        unique = uuid.uuid4().hex
        return f"recipes/{unique}_{safe}"

    def _delete_blob_if_exists(self, blob_name: str | None) -> None:
        if not blob_name or not self._bucket:
            return

        blob = self._bucket.blob(blob_name)

        try:
            blob.delete()
        except gcloud_exceptions.NotFound:
            # The blob may already have been removed manually; ignore.
            pass

    def _get_image_url(self, blob: storage.Blob) -> str:
        try:
            return blob.generate_signed_url(
                version="v4", method="GET", expiration=SIGNED_URL_EXPIRATION
            )
        except (ValueError, TypeError, AttributeError, auth_exceptions.GoogleAuthError):
            # Signed URLs require credentials capable of signing requests. In
            # development environments that lack such credentials we fall back
            # to the object's public URL. Buckets that use uniform
            # bucket-level access cannot use legacy ACLs (``make_public``), so
            # we simply return the public URL without modifying permissions.
            return blob.public_url


__all__ = ["FirestoreRecipeStorage"]
