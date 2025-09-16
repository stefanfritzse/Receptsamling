import os
from typing import Optional

from flask import Flask, flash, redirect, render_template, request, url_for

from .models import Recipe
from .storage import RecipeRepository

try:
    from .gcp_storage import FirestoreRecipeStorage
except ImportError:  # pragma: no cover - allows running tests without optional deps
    FirestoreRecipeStorage = None  # type: ignore[assignment]

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def create_app(storage: Optional[RecipeRepository] = None) -> Flask:
    """Create and configure the Flask application.

    Parameters
    ----------
    storage:
        Optional recipe repository. When ``None`` the application will use
        :class:`FirestoreRecipeStorage` configured through environment variables.
    """

    app = Flask(__name__)
    app.config.setdefault("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "development-secret-change-me")

    if storage is None:
        if FirestoreRecipeStorage is None:
            raise RuntimeError(
                "google-cloud-firestore is not installed. Install optional dependencies "
                "or pass an explicit storage backend to create_app."
            )
        storage = FirestoreRecipeStorage.from_env()
    app.config["RECIPE_STORAGE"] = storage

    @app.get("/")
    def index() -> str:
        recipes = list(app.config["RECIPE_STORAGE"].list_recipes())
        selected_id = request.args.get("selected")
        selected_recipe: Recipe | None = None

        if recipes:
            selected_recipe = next((recipe for recipe in recipes if recipe.id == selected_id), None)
            if selected_recipe is None:
                selected_recipe = recipes[0]
            selected_id = selected_recipe.id

        return render_template(
            "index.html",
            recipes=recipes,
            selected_recipe=selected_recipe,
            selected_id=selected_id,
            title="Recipe Library",
        )

    @app.post("/recipes")
    def create_recipe() -> str:
        storage_backend: RecipeRepository = app.config["RECIPE_STORAGE"]

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        ingredients_text = request.form.get("ingredients", "").strip()
        instructions = request.form.get("instructions", "").strip()
        image = request.files.get("image")

        if not title:
            flash("Please provide a recipe title.", "error")
            return redirect(url_for("index"))

        if image and not _allowed_image(image.filename):
            flash("Unsupported image format. Allowed formats: PNG, JPG, JPEG, GIF, WEBP.", "error")
            return redirect(url_for("index"))

        try:
            new_recipe = storage_backend.add_recipe(
                title=title,
                description=description,
                ingredients_text=ingredients_text,
                instructions=instructions,
                image=image,
            )
        except Exception as exc:  # pragma: no cover - defensive programming
            flash(f"Failed to save recipe: {exc}", "error")
        else:
            flash(f"Recipe '{title}' saved.", "success")

            if new_recipe and new_recipe.id:  # pragma: no branch - defensive for typing
                return redirect(url_for("index", selected=new_recipe.id))

        return redirect(url_for("index"))

    @app.get("/recipes/new")
    def new_recipe() -> str:
        return render_template("add_recipe.html", title="Add recipe")

    @app.get("/recipes/<recipe_id>/edit")
    def edit_recipe(recipe_id: str) -> str:
        storage_backend: RecipeRepository = app.config["RECIPE_STORAGE"]

        try:
            recipe = storage_backend.get_recipe(recipe_id)
        except KeyError:
            flash("Recipe not found.", "error")
            return redirect(url_for("index"))

        ingredients_text = "\n".join(recipe.ingredients)
        page_title = f"Edit {recipe.title}" if recipe.title else "Edit recipe"

        return render_template(
            "edit_recipe.html",
            recipe=recipe,
            ingredients_text=ingredients_text,
            title=page_title,
        )

    @app.post("/recipes/<recipe_id>")
    def update_recipe(recipe_id: str) -> str:
        storage_backend: RecipeRepository = app.config["RECIPE_STORAGE"]

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        ingredients_text = request.form.get("ingredients", "").strip()
        instructions = request.form.get("instructions", "").strip()
        image = request.files.get("image")
        remove_image = request.form.get("remove_image") == "1"

        if image and image.filename:
            remove_image = False

        if not title:
            flash("Please provide a recipe title.", "error")
            return redirect(url_for("edit_recipe", recipe_id=recipe_id))

        if image and not _allowed_image(image.filename):
            flash("Unsupported image format. Allowed formats: PNG, JPG, JPEG, GIF, WEBP.", "error")
            return redirect(url_for("edit_recipe", recipe_id=recipe_id))

        try:
            updated_recipe = storage_backend.update_recipe(
                recipe_id,
                title=title,
                description=description,
                ingredients_text=ingredients_text,
                instructions=instructions,
                image=image,
                remove_image=remove_image,
            )
        except KeyError:
            flash("Recipe not found.", "error")
            return redirect(url_for("index"))
        except Exception as exc:  # pragma: no cover - defensive programming
            flash(f"Failed to update recipe: {exc}", "error")
            return redirect(url_for("edit_recipe", recipe_id=recipe_id))

        flash(f"Recipe '{updated_recipe.title}' updated.", "success")
        return redirect(url_for("index", selected=updated_recipe.id))

    @app.post("/recipes/<recipe_id>/delete")
    def delete_recipe(recipe_id: str) -> str:
        storage_backend: RecipeRepository = app.config["RECIPE_STORAGE"]
        try:
            storage_backend.delete_recipe(recipe_id)
        except Exception as exc:  # pragma: no cover - defensive programming
            flash(f"Failed to delete recipe: {exc}", "error")
        else:
            flash("Recipe deleted.", "success")
        return redirect(url_for("index"))

    return app


def _allowed_image(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


__all__ = ["create_app", "Recipe"]
