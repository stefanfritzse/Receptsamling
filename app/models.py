from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Recipe:
    """Domain object representing a stored recipe."""

    id: str
    title: str
    description: str
    ingredients: List[str]
    instructions: str
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None


__all__ = ["Recipe"]
