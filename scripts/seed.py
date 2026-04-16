"""
Seed script — insert demo astronomy posts for testing.
Run inside the backend container:
  docker exec cosmic_backend python /app/scripts/seed.py
"""

import os
import sys
import uuid
import urllib.request
from pathlib import Path

sys.path.insert(0, "/app")

from app.database import SessionLocal
from app.models import User, UserProfile, Post

MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "/app/media"))

# ---------------------------------------------------------------------------
# Public-domain space images (NASA/ESA/Wikimedia)
# ---------------------------------------------------------------------------
SEED_POSTS = [
    {
        "title": "Samanyolu'nun Kalbinden",
        "caption": "Galaksimizin merkezine bu kadar yakın hissettiren bir kare. Hubble'ın gözünden.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Hubble_ultra_deep_field.jpg/1280px-Hubble_ultra_deep_field.jpg",
    },
    {
        "title": "Nebula Kıyısında",
        "caption": "Kartal Nebulası'nın sütunları — Yaratılışın Direkleri. James Webb teleskopu.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/68/Pillars_of_creation_2014_HST_WFC3-UVIS_full-res_denoised.jpg/800px-Pillars_of_creation_2014_HST_WFC3-UVIS_full-res_denoised.jpg",
    },
    {
        "title": "Satürn Halkası",
        "caption": "Cassini uzay aracından Satürn'ün görkemli halkaları. Evrenin sanatı.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Saturn_during_Equinox.jpg/1280px-Saturn_during_Equinox.jpg",
    },
    {
        "title": "Kızıl Gezegen",
        "caption": "Mars'ın yüzeyinden panoramik görünüm. Perseverance rover'dan.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/02/OSIRIS_Mars_true_color.jpg/1280px-OSIRIS_Mars_true_color.jpg",
    },
    {
        "title": "Andromeda Galaksisi",
        "caption": "2.5 milyon ışık yılı uzaktaki komşumuz. Dünya'dan çıplak gözle görülebilen en uzak nesne.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/98/Andromeda_Galaxy_%28with_h-alpha%29.jpg/1280px-Andromeda_Galaxy_%28with_h-alpha%29.jpg",
    },
    {
        "title": "Güneş Fırtınası",
        "caption": "SDO'nun kaydettiği güneş patlaması. Dünya'nın 10 katı büyüklüğünde plazma bulutları.",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/The_Sun_by_the_Atmospheric_Imaging_Assembly_of_NASA%27s_Solar_Dynamics_Observatory_-_20100819.jpg/1280px-The_Sun_by_the_Atmospheric_Imaging_Assembly_of_NASA%27s_Solar_Dynamics_Observatory_-_20100819.jpg",
    },
]


def _download_image(url: str, user_id: int) -> str:
    """Download image to media dir, return relative path."""
    ext = url.split(".")[-1].split("?")[0].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    dest_dir = MEDIA_DIR / "posts" / str(user_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    print(f"  Downloading {url[:60]}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CosmicExplorerSeed/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            dest.write_bytes(resp.read())
        return f"/media/posts/{user_id}/{filename}"
    except Exception as exc:
        print(f"  WARNING: download failed ({exc}), storing URL directly.")
        # Fall back to storing the URL directly (resolved without BASE_URL prefix)
        return url


def seed():
    db = SessionLocal()
    try:
        # ── Create demo user ────────────────────────────────────────────────
        user = db.query(User).filter_by(email="demo@cosmicexplorer.uk").first()
        if not user:
            user = User(email="demo@cosmicexplorer.uk", google_id=None)
            db.add(user)
            db.flush()
            print(f"Created demo user id={user.id}")
        else:
            print(f"Demo user already exists id={user.id}")

        profile = db.query(UserProfile).filter_by(user_id=user.id).first()
        if not profile:
            profile = UserProfile(
                user_id=user.id,
                username="cosmic_demo",
                display_name="Cosmic Demo",
                bio="Evrenin derinliklerinden paylaşımlar.",
            )
            db.add(profile)
            db.flush()
            print("Created demo profile")

        # ── Create posts ────────────────────────────────────────────────────
        existing = db.query(Post).filter_by(user_id=user.id).count()
        if existing >= len(SEED_POSTS):
            print(f"Seed posts already exist ({existing} posts). Skipping.")
            return

        for i, data in enumerate(SEED_POSTS):
            image_path = _download_image(data["image_url"], user.id)
            post = Post(
                user_id=user.id,
                image_url=image_path,
                title=data["title"],
                caption=data["caption"],
                like_count=i * 7 + 3,
                comment_count=i * 2,
            )
            db.add(post)
            print(f"  Added post: {data['title']}")

        db.commit()
        print(f"\nSeed complete — {len(SEED_POSTS)} posts added.")

    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
