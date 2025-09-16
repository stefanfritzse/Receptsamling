from __future__ import annotations

from pathlib import Path
import sys
import uuid
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.models import Recipe


class InMemoryRecipeStorage:
    """Simple storage backend used for tests."""

    def __init__(self) -> None:
        self._recipes: list[Recipe] = []

    def list_recipes(self):
        return sorted(
            self._recipes,
            key=lambda recipe: recipe.created_at or datetime.min,
            reverse=True,
        )

    def add_recipe(
        self,
        *,
        title: str,
        description: str,
        ingredients_text: str,
        instructions: str,
        image,
    ) -> Recipe:
        ingredients = [line.strip() for line in ingredients_text.splitlines() if line.strip()]
        recipe = Recipe(
            id=uuid.uuid4().hex,
            title=title,
            description=description,
            ingredients=ingredients,
            instructions=instructions,
            image_url=None,
            created_at=datetime.utcnow(),
        )
        self._recipes.append(recipe)
        return recipe

    def delete_recipe(self, recipe_id: str) -> None:
        for index, recipe in enumerate(self._recipes):
            if recipe.id == recipe_id:
                self._recipes.pop(index)
                return
        raise KeyError(recipe_id)


def create_test_client():
    storage = InMemoryRecipeStorage()
    app = create_app(storage=storage)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return app.test_client(), storage


def test_index_shows_existing_recipes():
    client, storage = create_test_client()
    storage.add_recipe(
        title="Chocolate Cake",
        description="Rich and moist.",
        ingredients_text="flour\nsugar",
        instructions="Bake it.",
        image=None,
    )

    response = client.get("/")
    assert response.status_code == 200
    assert b"Chocolate Cake" in response.data


def test_can_add_recipe_via_form():
    client, storage = create_test_client()

    response = client.post(
        "/recipes",
        data={
            "title": "Summer Salad",
            "description": "Fresh veggies",
            "ingredients": "tomatoes\ncucumber",
            "instructions": "Mix everything.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    titles = [recipe.title for recipe in storage.list_recipes()]
    assert "Summer Salad" in titles
    assert "Recipe &#39;Summer Salad&#39; saved." in response.get_data(as_text=True)


def test_cannot_add_recipe_without_title():
    client, storage = create_test_client()

    response = client.post(
        "/recipes",
        data={"title": "", "description": ""},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert not list(storage.list_recipes())
    assert b"Please provide a recipe title." in response.data


def test_delete_recipe_removes_item():
    client, storage = create_test_client()
    recipe = storage.add_recipe(
        title="Tofu Stir Fry",
        description="Quick weeknight dinner",
        ingredients_text="tofu",
        instructions="Cook it.",
        image=None,
    )

    response = client.post(f"/recipes/{recipe.id}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert all(existing.id != recipe.id for existing in storage.list_recipes())
    assert b"Recipe deleted." in response.data
