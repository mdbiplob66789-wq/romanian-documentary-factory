#!/usr/bin/env python3
"""
NordRouter (router.cheap) image-generation client — единственный внешний API
во всём пайплайне (п.45 ТЗ: остальное работает офлайн).

Логика 1:1 перенесена из "eat for fun/generate_images.py" (уже проверена на
реальных 160 кадрах video_001): retry с exponential backoff, честная обработка
Retry-After, lstrip перед парсингом JSON (router.cheap шлёт ведущий \\n),
определение реального формата ответа по magic bytes, а не по расширению.
"""

import base64
import gzip
import json
import os
import random
import time

import requests
from dotenv import load_dotenv

load_dotenv()

URL = "https://router.cheap/v1/images/generations"
MODEL = "gpt-image-2"
MAX_ATTEMPTS = 5
BASE_BACKOFF = 5
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class GenerationError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.getenv("NORDROUTER_API_KEY")
    if not key:
        raise GenerationError("Нет NORDROUTER_API_KEY в .env")
    return key


def generate_image(prompt: str, size: str = "1536x864", quality: str = "high") -> tuple[bytes, str]:
    """
    Возвращает (image_bytes, ext) где ext — 'jpg' или 'png', по реальному формату ответа.
    Кидает GenerationError с понятным текстом при неустранимой ошибке.
    """
    headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "output_format": "jpeg",
        "n": 1,
    }

    response = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.post(URL, headers=headers, json=payload, timeout=300)
        except requests.RequestException as e:
            time.sleep(BASE_BACKOFF * (2 ** (attempt - 1)))
            continue

        if response.status_code == 200:
            break

        if response.status_code not in RETRYABLE_STATUSES:
            raise GenerationError(f"HTTP {response.status_code} (не повторяем): {response.text[:300]}")

        retry_after = response.headers.get("Retry-After")
        try:
            wait = float(retry_after) if retry_after else BASE_BACKOFF * (2 ** (attempt - 1))
        except ValueError:
            wait = BASE_BACKOFF * (2 ** (attempt - 1))
        wait += random.uniform(0, 1)
        time.sleep(wait)

    if response is None or response.status_code != 200:
        raise GenerationError(f"Не удалось получить изображение за {MAX_ATTEMPTS} попыток")

    raw = response.content
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)

    stripped = raw.lstrip()
    image_bytes = None
    if stripped[:1] in (b"{", b"["):
        data = json.loads(stripped.decode("utf-8"))
        item = data["data"][0]
        if "b64_json" in item:
            image_bytes = base64.b64decode(item["b64_json"])
        elif "url" in item:
            img = requests.get(item["url"], timeout=300)
            image_bytes = img.content
    else:
        image_bytes = raw

    if not image_bytes:
        raise GenerationError("Ответ 200, но изображение не извлечено")

    if image_bytes.startswith(b"\xff\xd8\xff"):
        return image_bytes, "jpg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return image_bytes, "png"
    raise GenerationError(f"Ответ не похож на изображение, head bytes: {image_bytes[:20]!r}")
