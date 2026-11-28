import os
from pathlib import Path
from uuid import uuid4


def validar_imagen(contenido: bytes, content_type: str | None) -> str:
    if content_type is not None and not content_type.lower().startswith("image/"):
        raise ValueError("El archivo no contiene una imagen compatible.")

    is_jpeg = contenido.startswith(b"\xff\xd8\xff")
    is_png = contenido.startswith(b"\x89PNG\r\n\x1a\n")
    is_gif = contenido.startswith((b"GIF87a", b"GIF89a"))
    is_webp = (
        len(contenido) >= 12
        and contenido.startswith(b"RIFF")
        and contenido[8:12] == b"WEBP"
    )
    if not any((is_jpeg, is_png, is_gif, is_webp)):
        raise ValueError("El archivo no contiene una imagen compatible.")

    if is_jpeg:
        return ".jpg"
    if is_png:
        return ".png"
    if is_gif:
        return ".gif"
    return ".webp"


def guardar_imagen(contenido: bytes, extension: str, ruta_base: str) -> str:
    directorio = Path(ruta_base)
    directorio.mkdir(parents=True, exist_ok=True)
    ruta = directorio / f"{uuid4().hex}{extension}"
    ruta.write_bytes(contenido)
    return ruta.as_posix()


def eliminar_imagen(ruta: str) -> None:
    try:
        os.unlink(ruta)
    except FileNotFoundError:
        pass
