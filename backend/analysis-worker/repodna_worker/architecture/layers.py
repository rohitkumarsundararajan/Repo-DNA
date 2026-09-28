from __future__ import annotations

from pathlib import Path


LAYER_KEYWORDS = {
    "controller": {
        "controller",
        "controllers",
        "route",
        "routes",
        "handler",
        "handlers",
        "view",
        "views",
    },
    "service": {
        "service",
        "services",
        "usecase",
        "usecases",
    },
    "repository": {
        "repository",
        "repositories",
        "repo",
        "repos",
        "dao",
        "models",
        "db",
    },
}


def classify_layer(path: str) -> str:
    """Classify a repository file into an architectural layer."""

    path_obj = Path(path)

    parts = [
        part.lower()
        for part in path_obj.parts
    ]

    filename = path_obj.stem.lower()

    # Check folder names first.
    for layer, keywords in LAYER_KEYWORDS.items():
        if any(part in keywords for part in parts[:-1]):
            return layer

    # Then check the filename.
    for layer, keywords in LAYER_KEYWORDS.items():
        if any(keyword in filename for keyword in keywords):
            return layer

    return "unknown"