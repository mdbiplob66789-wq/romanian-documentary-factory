"""
Работа с изображениями: проверка, определение формата, конвертация шотов в RGB JPEG.
Для references формат по умолчанию не меняется (см. convert_shot_to_jpeg vs. validate_and_sniff).
"""

from pathlib import Path

from PIL import Image

SHOT_JPEG_QUALITY = 95  # "высокое качество" по ТЗ


class ImageValidationError(ValueError):
    pass


def validate_image(path: Path) -> str:
    """
    Проверяет, что файл реально открывается как изображение, и возвращает
    его формат (PNG/JPEG/WEBP/...). Кидает понятную ошибку, если файл битый
    или это не изображение вовсе.
    """
    try:
        with Image.open(path) as img:
            img.verify()
    except Exception as e:
        raise ImageValidationError(f"Файл не открывается как изображение: {path.name} ({e})")

    # После verify() объект использовать нельзя — открываем заново, чтобы прочитать формат.
    with Image.open(path) as img:
        fmt = img.format
    if fmt is None:
        raise ImageValidationError(f"Не удалось определить формат изображения: {path.name}")
    return fmt


def convert_shot_to_jpeg(src_path: Path, dst_path: Path) -> None:
    """
    Приводит изображение шота к RGB JPEG высокого качества.
    Не меняет aspect ratio, не делает resize.
    Если у источника есть альфа-канал — расплющивает на белый фон
    (итоговый JPEG прозрачность не поддерживает).
    """
    with Image.open(src_path) as img:
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.split()[-1])
            rgb = background
        else:
            rgb = img.convert("RGB")

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        rgb.save(dst_path, "JPEG", quality=SHOT_JPEG_QUALITY, subsampling=0, optimize=True)


def copy_reference_as_is(src_path: Path, dst_path_no_ext: Path, detected_format: str) -> Path:
    """
    Для references сохраняем исходный формат как есть (важно для PNG с прозрачностью, п.9) —
    просто перекодируем через Pillow с тем же форматом, без потери альфа-канала.
    Возвращает итоговый путь (с правильным расширением).
    """
    ext_by_format = {
        "PNG": "png",
        "JPEG": "jpg",
        "WEBP": "webp",
    }
    ext = ext_by_format.get(detected_format)
    if ext is None:
        raise ImageValidationError(
            f"Неподдерживаемый формат reference: {detected_format}. "
            "Поддерживаются PNG, JPEG, WebP."
        )

    dst_path = dst_path_no_ext.with_suffix(f".{ext}")
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src_path) as img:
        save_kwargs = {}
        if detected_format == "JPEG":
            save_kwargs = {"quality": SHOT_JPEG_QUALITY, "subsampling": 0, "optimize": True}
        img.save(dst_path, detected_format, **save_kwargs)

    return dst_path
