"""One release identifier shared with the static frontend build."""
import json
from pathlib import Path

APP_VERSION=json.loads((Path(__file__).resolve().parents[1]/'app-version.json').read_text(encoding='utf-8'))['version']
