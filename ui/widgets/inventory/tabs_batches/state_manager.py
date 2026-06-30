import json
import os


RUNTIME_DIR = "runtime"
STATE_FILE = os.path.join(RUNTIME_DIR, "inventory_last_state.json")
LEGACY_STATE_FILE = "inventory_last_state.json"

# ============================================================
# 2. StateManager — حفظ/تحميل حالة النموذج على القرص
# ============================================================
class StateManager:
    """
    يقرأ ويكتب آخر حالة للنموذج من/إلى ملف JSON.
    """

    @staticmethod
    def save(state: dict) -> None:
        try:
            os.makedirs(RUNTIME_DIR, exist_ok=True)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[StateManager] Error saving: {e}")

    @staticmethod
    def load() -> dict:
        state_file = STATE_FILE if os.path.exists(STATE_FILE) else LEGACY_STATE_FILE
        if not os.path.exists(state_file):
            return {}
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[StateManager] Error loading: {e}")
            return {}

