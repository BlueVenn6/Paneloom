ASPECT_PRESETS = {
    "square": {
        "label": "Square 1:1",
        "size": "1024x1024",
        "ratio": "1:1",
        "platforms": "Instagram feed, general posts",
    },
    "portrait_4_5": {
        "label": "Portrait 4:5",
        "size": "1024x1280",
        "generation_size": "1024x1536",
        "ratio": "4:5",
        "platforms": "Instagram feed portrait",
    },
    "vertical_9_16": {
        "label": "Vertical 9:16",
        "size": "1024x1792",
        "generation_size": "1024x1536",
        "ratio": "9:16",
        "platforms": "Reels, Shorts, Stories, TikTok-style video",
    },
    "landscape_16_9": {
        "label": "Landscape 16:9",
        "size": "1792x1024",
        "generation_size": "1536x1024",
        "ratio": "16:9",
        "platforms": "YouTube, horizontal video",
    },
    "pin_2_3": {
        "label": "Pinterest 2:3",
        "size": "1024x1536",
        "ratio": "2:3",
        "platforms": "Pinterest standard pin",
    },
}


def get_aspect_presets() -> list[dict]:
    return [{"id": key, **value} for key, value in ASPECT_PRESETS.items()]


def resolve_generation_sizes(aspect_presets: list[str] | None, fallback_size: str) -> list[dict]:
    selected = [preset for preset in aspect_presets or [] if preset in ASPECT_PRESETS]
    if not selected:
        return [{"id": "default", "label": "Default", "size": fallback_size, "generation_size": fallback_size}]
    return [
        {
            "id": preset,
            "label": ASPECT_PRESETS[preset]["label"],
            "size": ASPECT_PRESETS[preset]["size"],
            "generation_size": ASPECT_PRESETS[preset].get("generation_size", ASPECT_PRESETS[preset]["size"]),
        }
        for preset in selected
    ]
