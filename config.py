import copy
import json
import logging
import os
import shutil
import sys
import threading
import time
from pathlib import Path


logger = logging.getLogger(__name__)
_CONFIG_LOCK = threading.RLock()

def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = _app_root()
CONFIG_FILE = BASE_DIR / "config.json"

DEFAULT_PRINT_SETTINGS = {
    "default": {
        "page_width_pixels": 576,
        "center_x": 288,
        "margin": 20,
        "line_spacing": 10,
        "bottom_margin": 50,
        "extra_bottom_feed_pixels": 100,
        "fonts": {
            "title": {"name": "Tahoma", "height": 36, "weight": 700},
            "normal_bold": {"name": "Tahoma", "height": 28, "weight": 700},
            "normal": {"name": "Tahoma", "height": 26, "weight": 400},
            "small": {"name": "Tahoma", "height": 22, "weight": 400},
        },
    },
    "compact": {
        "page_width_pixels": 576,
        "center_x": 288,
        "margin": 5,
        "line_spacing": 5,
        "bottom_margin": 15,
        "extra_bottom_feed_pixels": 30,
        "fonts": {
            "title": {"name": "Tahoma", "height": 30, "weight": 700},
            "normal_bold": {"name": "Tahoma", "height": 24, "weight": 700},
            "normal": {"name": "Tahoma", "height": 22, "weight": 400},
            "small": {"name": "Tahoma", "height": 18, "weight": 400},
        },
    },
    "xprinter365b": {
        "page_width_pixels": 566,
        "center_x": 283,
        "margin": 0,
        "line_spacing": 8,
        "bottom_margin": 40,
        "extra_bottom_feed_pixels": 70,
        "fonts": {
            "title": {"name": "Tahoma", "height": 34, "weight": 700},
            "normal_bold": {"name": "Tahoma", "height": 26, "weight": 700},
            "normal": {"name": "Tahoma", "height": 24, "weight": 400},
            "small": {"name": "Tahoma", "height": 20, "weight": 400},
        },
    },
}

DEFAULT_CONFIG = {
    "languages": {},
    "print_settings": DEFAULT_PRINT_SETTINGS,
    "auto_virtual_keyboard_enabled": False,
    "auto_virtual_keyboard_targets": {
        "line_edit": True,
        "text_edit": True,
        "spin_box": False,
        "editable_combo": False,
        "combo_box": False,
    },
}


def get_config_path() -> Path:
    return CONFIG_FILE


def _merge_dict(defaults: dict, data: dict) -> dict:
    merged = copy.deepcopy(defaults)
    for key, value in (data or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def save_full_config(data: dict) -> bool:
    """
    حفظ الإعدادات بآلية الكتابة الذرية (Atomic Write) مع إنشاء نسخة احتياطية تلقائية (Backup)
    لتجنب تلف الملف (Corruption) في حال انقطاع الكهرباء أو تزامن الخيوط أثناء الكتابة.
    """
    if not isinstance(data, dict) or not data:
        logger.warning("Refusing to overwrite config.json with empty or invalid data.")
        return False

    with _CONFIG_LOCK:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = CONFIG_FILE.with_suffix(".json.tmp")
        bak_file = CONFIG_FILE.with_suffix(".json.bak")

        try:
            with tmp_file.open("w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())

            if CONFIG_FILE.exists():
                try:
                    with CONFIG_FILE.open("r", encoding="utf-8") as check_f:
                        existing = json.load(check_f)
                    if isinstance(existing, dict) and existing:
                        shutil.copyfile(CONFIG_FILE, bak_file)
                except Exception as exc:
                    logger.warning(f"الملف الحالي غير سليم، لن يتم استبدال النسخة الاحتياطية السابقة: {exc}")

            last_exc = None
            for attempt in range(5):
                try:
                    os.replace(tmp_file, CONFIG_FILE)
                    last_exc = None
                    break
                except PermissionError as exc:
                    last_exc = exc
                    time.sleep(0.05 * (attempt + 1))
            if last_exc is not None:
                raise last_exc

            logger.info("تم حفظ الإعدادات بنجاح بآلية الكتابة الذرية الآمنة.")
            return True
        except Exception as exc:
            logger.error(f"فشل في حفظ الإعدادات بآلية الكتابة الذرية: {exc}")
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except OSError:
                    pass
            return False


def _write_default_config() -> None:
    save_full_config(DEFAULT_CONFIG)


def load_full_config() -> dict:
    with _CONFIG_LOCK:
        bak_file = CONFIG_FILE.with_suffix(".json.bak")

        if not CONFIG_FILE.exists():
            default_template = CONFIG_FILE.with_name("config.default.json")
            if bak_file.exists():
                logger.info("ملف config.json مفقود، جاري استعادته من النسخة الاحتياطية (config.json.bak).")
                try:
                    shutil.copyfile(bak_file, CONFIG_FILE)
                except Exception as exc:
                    logger.warning(f"فشل استعادة النسخة الاحتياطية: {exc}")
            elif default_template.exists():
                logger.info("ملف config.json مفقود، جاري إنشاؤه من القالب الافتراضي (config.default.json).")
                try:
                    shutil.copyfile(default_template, CONFIG_FILE)
                except Exception as exc:
                    logger.warning(f"فشل نسخ القالب الافتراضي: {exc}")
            else:
                try:
                    _write_default_config()
                    logger.info("config.json was missing and has been created with default settings.")
                except OSError as exc:
                    logger.warning(f"Could not create config.json, using in-memory defaults: {exc}")
                    return copy.deepcopy(DEFAULT_CONFIG)

        for attempt in range(3):
            try:
                with CONFIG_FILE.open("r", encoding="utf-8") as file:
                    loaded = json.load(file)
                if isinstance(loaded, dict):
                    return _merge_dict(DEFAULT_CONFIG, loaded)
                raise ValueError("config.json root is not a JSON object")
            except (json.JSONDecodeError, ValueError, OSError) as exc:
                if isinstance(exc, PermissionError) and attempt < 2:
                    time.sleep(0.05 * (attempt + 1))
                    continue
                logger.error(f"تلف ملف config.json مكتشف ({exc}). جاري محاولة الاستعادة من النسخة الاحتياطية (config.json.bak)...")
                if bak_file.exists():
                    try:
                        with bak_file.open("r", encoding="utf-8") as b_file:
                            backup_data = json.load(b_file)
                        if isinstance(backup_data, dict):
                            shutil.copyfile(bak_file, CONFIG_FILE)
                            logger.info("تم استعادة إعدادات config.json بنجاح من النسخة الاحتياطية.")
                            return _merge_dict(DEFAULT_CONFIG, backup_data)
                    except Exception as backup_exc:
                        logger.error(f"فشل استعادة النسخة الاحتياطية، سيتم استخدام الإعدادات الافتراضية: {backup_exc}")
                return copy.deepcopy(DEFAULT_CONFIG)
        return copy.deepcopy(DEFAULT_CONFIG)


def update_config_values(updater) -> bool:
    """Safely read-modify-write config.json under lock without dropping unrelated settings."""
    with _CONFIG_LOCK:
        current = load_full_config()
        if callable(updater):
            updated = updater(copy.deepcopy(current))
            if isinstance(updated, dict):
                current = updated
        elif isinstance(updater, dict):
            current = _merge_dict(current, updater)
        return save_full_config(current)


def load_config():
    data = load_full_config()
    logger.info("config.json settings loaded.")
    return data.get("languages", {}), data.get("print_settings", copy.deepcopy(DEFAULT_PRINT_SETTINGS))


languages, print_settings = load_config()


def reload_config():
    global languages, print_settings
    languages, print_settings = load_config()
    logger.info("Configuration reloaded.")
