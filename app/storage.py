from __future__ import annotations

from typing import Iterable, Protocol

from werkzeug.datastructures import FileStorage

from .models import Recipe


class RecipeRepository(Protocol):
    """Protocol describing the behaviour required by the web layer."""

    def list_recipes(self) -> Iterable[Recipe]:
        """Return an iterable of stored recipes ordered newest first."""

    def add_recipe(
        self,
        *,
        title: str,
        description: str,
        ingredients_text: str,
        instructions: str,
        image: FileStorage | None,
    ) -> Recipe:
        """Persist a new recipe and return the stored instance."""

    def delete_recipe(self, recipe_id: str) -> None:
        """Remove a recipe and any associated assets."""


__all__ = ["RecipeRepository"]
