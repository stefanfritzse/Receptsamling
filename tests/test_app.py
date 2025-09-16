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

    def get_recipe(self, recipe_id: str) -> Recipe:
        for recipe in self._recipes:
            if recipe.id == recipe_id:
                return recipe
        raise KeyError(recipe_id)

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

    def update_recipe(
        self,
        recipe_id: str,
        *,
        title: str,
        description: str,
        ingredients_text: str,
        instructions: str,
        image,
    ) -> Recipe:
        recipe = self.get_recipe(recipe_id)
        ingredients = [line.strip() for line in ingredients_text.splitlines() if line.strip()]
        recipe.title = title
        recipe.description = description
        recipe.ingredients = ingredients
        recipe.instructions = instructions
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


def test_edit_recipe_page_prefills_current_values():
    client, storage = create_test_client()
    recipe = storage.add_recipe(
        title="Pasta Salad",
        description="Perfect for picnics",
        ingredients_text="pasta\ntomatoes",
        instructions="Mix together.",
        image=None,
    )

    response = client.get(f"/recipes/{recipe.id}/edit")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "value=\"Pasta Salad\"" in page
    assert "Perfect for picnics" in page
    assert "pasta\ntomatoes" in page


def test_can_update_recipe_via_form():
    client, storage = create_test_client()
    recipe = storage.add_recipe(
        title="Veggie Curry",
        description="Mild and creamy",
        ingredients_text="carrots",
        instructions="Cook gently.",
        image=None,
    )

    response = client.post(
        f"/recipes/{recipe.id}",
        data={
            "title": "Spicy Veggie Curry",
            "description": "Now with a kick",
            "ingredients": "carrots\npotatoes",
            "instructions": "Add spices.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    updated = storage.get_recipe(recipe.id)
    assert updated.title == "Spicy Veggie Curry"
    assert updated.description == "Now with a kick"
    assert updated.ingredients == ["carrots", "potatoes"]
    assert updated.instructions == "Add spices."
    assert "Recipe &#39;Spicy Veggie Curry&#39; updated." in response.get_data(as_text=True)


def test_cannot_update_recipe_without_title():
    client, storage = create_test_client()
    recipe = storage.add_recipe(
        title="Soup",
        description="Warm and cozy",
        ingredients_text="water",
        instructions="Boil.",
        image=None,
    )

    response = client.post(
        f"/recipes/{recipe.id}",
        data={
            "title": "",
            "description": "Still warm",
            "ingredients": "water",
            "instructions": "Boil longer.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Please provide a recipe title." in response.data
    assert storage.get_recipe(recipe.id).title == "Soup"
