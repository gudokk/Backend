from fastapi import APIRouter, HTTPException
import os
from pathlib import Path

router = APIRouter()

@router.get("/api/resort-images/{resort_id}")
def get_resort_images(resort_id: int):
    base_path = Path(__file__).resolve().parent.parent
    images_dir = base_path / "app" / "static" / "images" / "resorts" / str(resort_id)

    if not images_dir.exists() or not images_dir.is_dir():
        raise HTTPException(status_code=404, detail="Images not found")

    images = []
    for i, file in enumerate(sorted(images_dir.iterdir())):
        if file.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
            static_path = file.relative_to(base_path / "app" / "static")
            images.append({
                "id": i + 1,
                "image": f"/static/{static_path.as_posix()}"
            })

    return images
