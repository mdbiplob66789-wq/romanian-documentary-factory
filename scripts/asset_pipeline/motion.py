"""
Зеркало утверждённой motion-механики из src/Root.jsx — используется ТОЛЬКО для
независимой QC-проверки (render_qc.json), не для рендера. Если когда-нибудь
Root.jsx поменяют, а это зеркало — нет, QC начнёт явно расходиться и упадёт,
а не молча соврёт "всё ок".

Значения (low=4%, medium=7%, hard cap 8%) и формулы zoom_in/zoom_out/pan_left/
pan_right/static — 1:1 копия JS-версии, math не переизобретена.
"""

VALID_MOTIONS = {"static", "zoom_in", "zoom_out", "pan_left", "pan_right"}
VALID_INTENSITIES = {"low", "medium"}

AMPLITUDE = {"low": 0.04, "medium": 0.07}
HARD_CAP = 0.08  # scale никогда не должен уходить дальше 1 + HARD_CAP

PAN_TRAVEL_PERCENT = {"low": 1.2, "medium": 1.7}
PAN_BASE_SCALE = 1.04  # предварительный zoom, чтобы pan не показал пустые края


class UnknownMotionError(ValueError):
    pass


def motion_bounds(motion: str, intensity: str) -> dict:
    """
    Возвращает {start_scale, end_scale, translate_start: (x,y), translate_end: (x,y)}
    для указанных motion/intensity — независимо пересчитано, не взято из Remotion.
    Unknown motion type -> исключение (FAIL, а не fallback на случайный zoom, п.10 ТЗ).
    """
    if motion not in VALID_MOTIONS:
        raise UnknownMotionError(f"Unknown motion type: {motion!r}")
    if intensity not in VALID_INTENSITIES:
        raise UnknownMotionError(f"Unknown intensity: {intensity!r}")

    amplitude = AMPLITUDE[intensity]

    if motion == "static":
        return {"start_scale": 1.0, "end_scale": 1.0, "translate_start": (0.0, 0.0), "translate_end": (0.0, 0.0)}

    if motion == "zoom_in":
        return {"start_scale": 1.0, "end_scale": 1.0 + amplitude, "translate_start": (0.0, 0.0), "translate_end": (0.0, 0.0)}

    if motion == "zoom_out":
        return {"start_scale": 1.0 + amplitude, "end_scale": 1.0, "translate_start": (0.0, 0.0), "translate_end": (0.0, 0.0)}

    travel = PAN_TRAVEL_PERCENT[intensity]
    if motion == "pan_left":
        return {
            "start_scale": PAN_BASE_SCALE, "end_scale": PAN_BASE_SCALE,
            "translate_start": (travel, -0.1), "translate_end": (-travel, 0.1),
        }
    if motion == "pan_right":
        return {
            "start_scale": PAN_BASE_SCALE, "end_scale": PAN_BASE_SCALE,
            "translate_start": (-travel, 0.1), "translate_end": (travel, -0.1),
        }

    raise UnknownMotionError(f"Unhandled motion type: {motion!r}")  # не должно достигаться


def max_scale(bounds: dict) -> float:
    return max(bounds["start_scale"], bounds["end_scale"])
