import os
import io
from pathlib import Path
from dataclasses import dataclass
from PIL import Image,UnidentifiedImageError
from ..config import settings

@dataclass
class StoredImage:
    url: str
    public_id: str
    provider: str

class ImageStorage:
    def __init__(self):
        self.cloudinary_ready=all([settings.cloudinary_cloud_name,settings.cloudinary_api_key,settings.cloudinary_api_secret])
        if self.cloudinary_ready:
            import cloudinary
            cloudinary.config(cloud_name=settings.cloudinary_cloud_name,api_key=settings.cloudinary_api_key,api_secret=settings.cloudinary_api_secret,secure=True)

    def upload(self,data:bytes,content_type:str)->StoredImage:
        if self.cloudinary_ready:
            import cloudinary.uploader
            result=cloudinary.uploader.upload(data,folder="civiclens/issues",resource_type="image",overwrite=False)
            return StoredImage(result["secure_url"],result["public_id"],"cloudinary")
        ext={"image/jpeg":"jpg","image/png":"png","image/webp":"webp"}[content_type]
        name=f"{os.urandom(16).hex()}.{ext}"; Path(settings.upload_dir).mkdir(parents=True,exist_ok=True); Path(settings.upload_dir,name).write_bytes(data)
        return StoredImage(f"/uploads/{name}",name,"local")

    def sanitize(self,data:bytes,content_type:str)->bytes:
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                if image.width*image.height>25_000_000:raise ValueError("Image dimensions are too large")
                image=image.convert("RGB") if content_type in {"image/jpeg","image/webp"} else image.convert("RGBA")
                out=io.BytesIO();fmt={"image/jpeg":"JPEG","image/png":"PNG","image/webp":"WEBP"}[content_type];image.save(out,format=fmt,quality=88,optimize=True)
                return out.getvalue()
        except (UnidentifiedImageError,OSError):raise ValueError("The uploaded file is not a valid image")

    def delete(self,public_id:str|None):
        if not public_id:return
        if self.cloudinary_ready:
            import cloudinary.uploader
            cloudinary.uploader.destroy(public_id)
        else:
            path=Path(settings.upload_dir,Path(public_id).name)
            if path.exists():path.unlink()

storage=ImageStorage()
