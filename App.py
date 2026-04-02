import json
import re
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

# ============================================================
# Config
# ============================================================

st.set_page_config(
    page_title="Мастер Боевых Столкновений",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_TITLE = "⚔️ Мастер Боевых Столкновений"

DATA_DIR = Path("data")
MONSTERS_DIR = DATA_DIR / "monsters"
USERS_FILE = DATA_DIR / "users.json"

MONSTER_DATABASES = {
    "Базовая база монстров": "monsters_base.json",
    "Кастомная база монстров": "monsters_custom.json",
}

STATUS_LIBRARY = {
    "Ослеплён": "Существо не видит и автоматически проваливает проверки, основанные на зрении.",
    "Очарован": "Существо не может атаковать очаровавшего и не может делать против него вредоносные действия.",
    "Оглох": "Существо не слышит и автоматически проваливает проверки, основанные на слухе.",
    "Испуган": "Существо совершает проверки характеристик и атаки с помехой, пока источник страха в пределах видимости.",
    "Схвачен": "Скорость существа становится 0.",
    "Недееспособен": "Существо не может совершать действия или реакции.",
    "Невидимый": "Существо невозможно увидеть без магии или особого чувства.",
    "Парализован": "Существо недееспособно, не может двигаться или говорить.",
    "Окаменён": "Существо превращено в твёрдую неподвижную субстанцию.",
    "Отравлен": "Существо совершает броски атаки и проверки характеристик с помехой.",
    "Сбит с ног": "Единственный вариант перемещения — ползти, пока не встанет.",
    "Скован": "Скорость 0, атаки по существу с преимуществом.",
    "Оглушён": "Существо недееспособно, не может двигаться.",
    "Без сознания": "Существо недееспособно, не осознаёт происходящее.",
    "Мёртв": "Существо мертво и исключается из очереди ходов, если это монстр.",
}

COMBATANT_TYPE_LABELS = {
    "player": "Игрок",
    "npc": "NPC",
    "monster": "Монстр",
}

COMBATANT_TYPE_BORDER = {
    "player": "rgba(96, 165, 250, 0.95)",
    "npc": "rgba(148, 163, 184, 0.95)",
    "monster": "rgba(248, 113, 113, 0.95)",
}


# ============================================================
# Setup
# ============================================================

def ensure_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    MONSTERS_DIR.mkdir(exist_ok=True)

    defaults = {
        USERS_FILE: [{"username": "admin", "password": "admin"}],
    }

    for path, payload in defaults.items():
        if not path.exists():
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for file_name in MONSTER_DATABASES.values():
        db_path = MONSTERS_DIR / file_name
        if not db_path.exists():
            db_path.write_text("[]", encoding="utf-8")


ensure_storage()


# ============================================================
# JSON helpers
# ============================================================

def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ============================================================
# Parsing and normalization
# ============================================================

def extract_first_int(value: Any, fallback: int = 0) -> int:
    if value is None:
        return fallback
    match = re.search(r"-?\d+", str(value))
    return int(match.group()) if match else fallback


def normalize_monster(raw: Dict[str, Any]) -> Dict[str, Any]:
    armor_class_raw = raw.get("Armor Class", "0")
    hp_raw = raw.get("Hit Points", "0")
    return {
        "name": raw.get("name", "Безымянный монстр"),
        "meta": raw.get("meta", ""),
        "armor_class_raw": armor_class_raw,
        "hit_points_raw": hp_raw,
        "armor_class_value": extract_first_int(armor_class_raw, 0),
        "hit_points_value": extract_first_int(hp_raw, 0),
        "speed": raw.get("Speed", "—"),
        "str": raw.get("STR", "—"),
        "str_mod": raw.get("STR_mod", ""),
        "dex": raw.get("DEX", "—"),
        "dex_mod": raw.get("DEX_mod", ""),
        "con": raw.get("CON", "—"),
        "con_mod": raw.get("CON_mod", ""),
        "int": raw.get("INT", "—"),
        "int_mod": raw.get("INT_mod", ""),
        "wis": raw.get("WIS", "—"),
        "wis_mod": raw.get("WIS_mod", ""),
        "cha": raw.get("CHA", "—"),
        "cha_mod": raw.get("CHA_mod", ""),
        "saving_throws": raw.get("Saving Throws", "—"),
        "skills": raw.get("Skills", "—"),
        "senses": raw.get("Senses", "—"),
        "languages": raw.get("Languages", "—"),
        "challenge": raw.get("Challenge", "—"),
        "traits": raw.get("Traits", ""),
        "actions": raw.get("Actions", ""),
        "legendary_actions": raw.get("Legendary Actions", ""),
        "img_url": raw.get("img_url", ""),
    }


def load_monster_database(db_title: str) -> List[Dict[str, Any]]:
    file_name = MONSTER_DATABASES[db_title]
    raw_monsters = load_json(MONSTERS_DIR / file_name, [])
    monsters = [normalize_monster(m) for m in raw_monsters if isinstance(m, dict)]
    monsters.sort(key=lambda x: x["name"].lower())
    return monsters


# ============================================================
# Session state
# ============================================================

def init_state() -> None:
    defaults = {
        "is_authenticated": False,
        "auth_user": None,
        "screen": "prepare",
        "selected_db_title": list(MONSTER_DATABASES.keys())[0],
        "encounter_name_input": "",
        "create_combatants": [],
        "battle_state": None,
        "selected_monster_name": None,
        "show_monster_modal": False,
        "party_import_nonce": 0,
        "encounter_import_nonce": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


# ============================================================
# Domain helpers
# ============================================================

def clone_combatants_with_new_ids(combatants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cloned = deepcopy(combatants)
    for combatant in cloned:
        combatant["id"] = str(uuid.uuid4())
    return cloned


def new_combatant(
    name: str,
    combatant_type: str,
    max_hp: int,
    current_hp: int,
    armor_class: int,
    initiative: int,
    monster_ref: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "type": combatant_type,
        "max_hp": int(max_hp),
        "current_hp": int(current_hp),
        "armor_class": int(armor_class),
        "initiative": int(initiative),
        "statuses": [],
        "monster_ref": monster_ref,
        "sort_order": 0,
    }


def assign_sort_order(combatants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for index, combatant in enumerate(combatants):
        combatant["sort_order"] = index
    return combatants


def sort_prepare_combatants(combatants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    assign_sort_order(combatants)
    return sorted(combatants, key=lambda c: (-int(c["initiative"]), int(c["sort_order"])))


def sort_battle_combatants(combatants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    assign_sort_order(combatants)
    living = [c for c in combatants if not (c["type"] == "monster" and "Мёртв" in c.get("statuses", []))]
    dead_monsters = [c for c in combatants if c["type"] == "monster" and "Мёртв" in c.get("statuses", [])]
    living_sorted = sorted(living, key=lambda c: (-int(c["initiative"]), int(c["sort_order"])))
    dead_sorted = sorted(dead_monsters, key=lambda c: (-int(c["initiative"]), int(c["sort_order"])))
    return living_sorted + dead_sorted


def get_roster_summary(combatants: List[Dict[str, Any]]) -> Dict[str, int]:
    return {
        "players": sum(1 for c in combatants if c["type"] == "player"),
        "npcs": sum(1 for c in combatants if c["type"] == "npc"),
        "monsters": sum(1 for c in combatants if c["type"] == "monster"),
    }


def build_party_export(combatants: List[Dict[str, Any]]) -> Dict[str, Any]:
    party = [deepcopy(c) for c in combatants if c["type"] in {"player", "npc"}]
    return {
        "kind": "party",
        "version": 1,
        "combatants": party,
        "exported_at": datetime.utcnow().isoformat(),
    }


def build_encounter_export(name: str, combatants: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "kind": "encounter",
        "version": 1,
        "name": name.strip() or "Несохранённое столкновение",
        "combatants": deepcopy(combatants),
        "exported_at": datetime.utcnow().isoformat(),
    }


def import_party_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("JSON должен быть объектом")
    if payload.get("kind") != "party":
        raise ValueError("Это не JSON отряда")
    combatants = payload.get("combatants")
    if not isinstance(combatants, list):
        raise ValueError("Неверная структура combatants")
    filtered = [c for c in combatants if isinstance(c, dict) and c.get("type") in {"player", "npc"}]
    return clone_combatants_with_new_ids(filtered)


def import_encounter_payload(payload: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    if not isinstance(payload, dict):
        raise ValueError("JSON должен быть объектом")
    if payload.get("kind") != "encounter":
        raise ValueError("Это не JSON столкновения")
    combatants = payload.get("combatants")
    if not isinstance(combatants, list):
        raise ValueError("Неверная структура combatants")
    name = str(payload.get("name", "Импортированное столкновение"))
    filtered = [c for c in combatants if isinstance(c, dict)]
    return name, clone_combatants_with_new_ids(filtered)


def build_battle_state(name: str, combatants: List[Dict[str, Any]]) -> Dict[str, Any]:
    battle_combatants = clone_combatants_with_new_ids(combatants)
    for combatant in battle_combatants:
        normalize_combatant_hp_and_statuses(combatant)
    battle_combatants = sort_battle_combatants(battle_combatants)
    return {
        "encounter_id": str(uuid.uuid4()),
        "encounter_name": name.strip() or "Несохранённое столкновение",
        "combatants": battle_combatants,
        "round": 1,
        "turn_index": 0,
    }


# ============================================================
# Auth
# ============================================================

def check_credentials(username: str, password: str) -> bool:
    users = load_json(USERS_FILE, [])
    return any(u.get("username") == username and u.get("password") == password for u in users)


def render_login() -> None:
    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        st.markdown("<div class='hero-card'>", unsafe_allow_html=True)
        st.title(APP_TITLE)
        st.subheader("Вход")
        with st.form("login_form"):
            username = st.text_input("Логин")
            password = st.text_input("Пароль", type="password")
            submitted = st.form_submit_button("Войти", use_container_width=True)
        if submitted:
            if check_credentials(username, password):
                st.session_state.is_authenticated = True
                st.session_state.auth_user = username
                st.rerun()
            else:
                st.error("Неверный логин или пароль")
        st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# Battle logic
# ============================================================

def get_active_combatant(battle_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    combatants = battle_state["combatants"]
    if not combatants:
        return None
    index = min(max(battle_state["turn_index"], 0), len(combatants) - 1)
    return combatants[index]


def normalize_combatant_hp_and_statuses(combatant: Dict[str, Any]) -> None:
    combatant["current_hp"] = max(0, min(int(combatant["current_hp"]), int(combatant["max_hp"])))
    statuses = set(combatant.get("statuses", []))

    if combatant["current_hp"] <= 0:
        if combatant["type"] == "monster":
            statuses.discard("Без сознания")
            statuses.add("Мёртв")
        else:
            statuses.discard("Мёртв")
            statuses.add("Без сознания")
    else:
        statuses.discard("Мёртв")
        statuses.discard("Без сознания")

    combatant["statuses"] = sorted(statuses)


def active_turn_is_skippable(combatant: Dict[str, Any]) -> bool:
    return combatant["type"] == "monster" and "Мёртв" in combatant.get("statuses", [])


def rebuild_battle_sort_preserving_active(battle_state: Dict[str, Any]) -> None:
    active = get_active_combatant(battle_state)
    active_id = active["id"] if active else None
    battle_state["combatants"] = sort_battle_combatants(battle_state["combatants"])

    if active_id:
        for idx, combatant in enumerate(battle_state["combatants"]):
            if combatant["id"] == active_id:
                battle_state["turn_index"] = idx
                return
    battle_state["turn_index"] = 0


def next_valid_turn_index(battle_state: Dict[str, Any], start_index: int) -> Tuple[int, bool]:
    combatants = battle_state["combatants"]
    if not combatants:
        return 0, False

    total = len(combatants)
    wrapped = False
    index = start_index

    for _ in range(total):
        if index >= total:
            index = 0
            wrapped = True
        current = combatants[index]
        if not active_turn_is_skippable(current):
            return index, wrapped
        index += 1

    return 0, wrapped


def next_turn() -> None:
    battle_state = st.session_state.battle_state
    if not battle_state or not battle_state["combatants"]:
        return

    current_index = battle_state["turn_index"]
    next_index, wrapped = next_valid_turn_index(battle_state, current_index + 1)
    battle_state["turn_index"] = next_index
    if wrapped:
        battle_state["round"] += 1


def apply_hp_delta(combatant_id: str, delta: int) -> None:
    battle_state = st.session_state.battle_state
    if not battle_state:
        return

    for combatant in battle_state["combatants"]:
        if combatant["id"] == combatant_id:
            combatant["current_hp"] = int(combatant["current_hp"]) + int(delta)
            normalize_combatant_hp_and_statuses(combatant)
            break

    rebuild_battle_sort_preserving_active(battle_state)
    active = get_active_combatant(battle_state)
    if active and active_turn_is_skippable(active):
        next_turn()


def update_combatant_statuses(combatant_id: str, statuses: List[str]) -> None:
    battle_state = st.session_state.battle_state
    if not battle_state:
        return

    for combatant in battle_state["combatants"]:
        if combatant["id"] == combatant_id:
            combatant["statuses"] = sorted(set(statuses))
            normalize_combatant_hp_and_statuses(combatant)
            break

    rebuild_battle_sort_preserving_active(battle_state)


def update_combatant_initiative(combatant_id: str, new_initiative: int) -> None:
    battle_state = st.session_state.battle_state
    if not battle_state:
        return

    for combatant in battle_state["combatants"]:
        if combatant["id"] == combatant_id:
            combatant["initiative"] = int(new_initiative)
            break

    rebuild_battle_sort_preserving_active(battle_state)


# ============================================================
# UI helpers
# ============================================================

def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }
        .stApp {
            background: #0f131a;
        }
        .block-container {
            padding-top: 0.7rem;
            padding-bottom: 1.2rem;
            max-width: 1800px;
        }
        .hero-card {
            border: 1px solid rgba(255,255,255,0.08);
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
            padding: 24px;
            margin-top: 8vh;
        }
        .status-chip, .turn-chip, .type-chip {
            display: inline-block;
            border-radius: 999px;
            padding: 3px 9px;
            margin-right: 6px;
            margin-top: 2px;
            font-size: 0.78rem;
            font-weight: 600;
            border: 1px solid rgba(255,255,255,0.08);
            background: rgba(255,255,255,0.06);
        }
        .turn-chip {
            background: rgba(250, 204, 21, 0.18);
            border-color: rgba(250, 204, 21, 0.35);
        }
        .section-title {
            font-size: 1.02rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        .sidebar-nav-title {
            margin-top: 0.2rem;
            margin-bottom: 0.45rem;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def header_bar() -> None:
    st.title(APP_TITLE)


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("<div class='sidebar-nav-title'>Навигация</div>", unsafe_allow_html=True)
        if st.button(
            "Подготовка столкновения",
            use_container_width=True,
            type="primary" if st.session_state.screen == "prepare" else "secondary",
            key="sidebar_nav_prepare",
        ):
            st.session_state.screen = "prepare"
            st.rerun()
        if st.button(
            "Проведение боя",
            use_container_width=True,
            type="primary" if st.session_state.screen == "battle" else "secondary",
            key="sidebar_nav_battle",
        ):
            st.session_state.screen = "battle"
            st.rerun()

        st.markdown("---")
        st.markdown(f"**Пользователь:** {st.session_state.auth_user}")
        if st.button("Выйти", use_container_width=True, key="sidebar_logout"):
            st.session_state.is_authenticated = False
            st.session_state.auth_user = None
            st.session_state.screen = "prepare"
            st.session_state.battle_state = None
            st.session_state.selected_monster_name = None
            st.session_state.show_monster_modal = False
            st.rerun()


def render_status_chips(statuses: List[str]) -> None:
    if not statuses:
        return
    display = statuses[:2]
    extra = len(statuses) - len(display)
    html = "".join(f"<span class='status-chip'>{s}</span>" for s in display)
    if extra > 0:
        html += f"<span class='status-chip'>+{extra}</span>"
    st.markdown(html, unsafe_allow_html=True)


def get_monster_by_name(monsters: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    for monster in monsters:
        if monster["name"] == name:
            return monster
    return None


def open_monster_modal(monster_name: str) -> None:
    st.session_state.selected_monster_name = monster_name
    st.session_state.show_monster_modal = True


def close_monster_modal() -> None:
    st.session_state.show_monster_modal = False


# ============================================================
# Prepare encounter screen
# ============================================================

def render_prepare_action_bar() -> None:
    st.subheader("Подготовка столкновения")
    c1, c2, c3 = st.columns([1.7, 1.2, 1.0])

    with c1:
        st.session_state.encounter_name_input = st.text_input(
            "Название столкновения",
            value=st.session_state.encounter_name_input,
            key="encounter_name_input_widget",
        )

    with c2:
        st.session_state.selected_db_title = st.selectbox(
            "База монстров",
            options=list(MONSTER_DATABASES.keys()),
            index=list(MONSTER_DATABASES.keys()).index(st.session_state.selected_db_title),
        )

    with c3:
        st.write("")
        if st.button("Начать бой", use_container_width=True, type="primary", key="start_battle_main"):
            if not st.session_state.create_combatants:
                st.error("Сначала добавь участников")
            else:
                st.session_state.battle_state = build_battle_state(
                    st.session_state.encounter_name_input,
                    st.session_state.create_combatants,
                )
                st.session_state.screen = "battle"
                st.rerun()


def reset_party_import_uploader() -> None:
    st.session_state.party_import_nonce += 1


def reset_encounter_import_uploader() -> None:
    st.session_state.encounter_import_nonce += 1


def render_json_imports() -> None:
    st.markdown("<div class='section-title'>Импорт JSON</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        party_key = f"party_json_import_{st.session_state.party_import_nonce}"
        party_file = st.file_uploader("Отряд", type=["json"], key=party_key)
        if party_file is not None:
            st.caption(f"Выбран файл: {party_file.name}")
        if st.button("Импортировать отряд", use_container_width=True, key=f"import_party_btn_{st.session_state.party_import_nonce}"):
            if party_file is None:
                st.warning("Сначала выбери файл отряда")
            else:
                try:
                    payload = json.load(party_file)
                    imported = import_party_payload(payload)
                    st.session_state.create_combatants.extend(imported)
                    st.session_state.create_combatants = sort_prepare_combatants(st.session_state.create_combatants)
                    reset_party_import_uploader()
                    st.success(f"Импортировано участников отряда: {len(imported)}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка импорта отряда: {e}")

    with c2:
        encounter_key = f"encounter_json_import_{st.session_state.encounter_import_nonce}"
        encounter_file = st.file_uploader("Столкновение", type=["json"], key=encounter_key)
        if encounter_file is not None:
            st.caption(f"Выбран файл: {encounter_file.name}")
        if st.button("Импортировать столкновение", use_container_width=True, key=f"import_encounter_btn_{st.session_state.encounter_import_nonce}"):
            if encounter_file is None:
                st.warning("Сначала выбери файл столкновения")
            else:
                try:
                    payload = json.load(encounter_file)
                    name, imported = import_encounter_payload(payload)
                    st.session_state.encounter_name_input = name
                    st.session_state.create_combatants = sort_prepare_combatants(imported)
                    reset_encounter_import_uploader()
                    st.success(f"Импортировано участников столкновения: {len(imported)}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Ошибка импорта столкновения: {e}")


def render_add_manual_combatant_tab() -> None:
    with st.form("add_manual_combatant_form", clear_on_submit=True):
        c1, c2 = st.columns(2)

        with c1:
            name = st.text_input("Имя")
            combatant_type = st.selectbox(
                "Тип",
                options=["player", "npc"],
                format_func=lambda x: COMBATANT_TYPE_LABELS[x],
            )
            initiative = st.number_input("Инициатива", value=0, step=1)

        with c2:
            max_hp = st.number_input("Макс HP", min_value=1, value=10, step=1)
            current_hp = st.number_input("Текущий HP", min_value=0, value=10, step=1)
            armor_class = st.number_input("Класс брони", min_value=0, value=10, step=1)

        submitted = st.form_submit_button("Добавить участника", use_container_width=True)

    if submitted:
        if not name.strip():
            st.error("Укажи имя участника")
            return

        st.session_state.create_combatants.append(
            new_combatant(
                name=name,
                combatant_type=combatant_type,
                max_hp=int(max_hp),
                current_hp=int(min(current_hp, max_hp)),
                armor_class=int(armor_class),
                initiative=int(initiative),
            )
        )
        st.session_state.create_combatants = sort_prepare_combatants(st.session_state.create_combatants)
        st.success(f"Добавлен: {name}")


def render_add_monster_tab(monsters: List[Dict[str, Any]]) -> None:
    query = st.text_input("Монстр", placeholder="Начни вводить имя монстра", key="monster_combined_search")

    if len(query.strip()) < 2:
        st.info("Введи 2–3 символа для поиска монстра")
        return

    q = query.strip().lower()
    matches = [m for m in monsters if q in m["name"].lower()][:100]

    if not matches:
        st.warning("Монстры не найдены")
        return

    selected_name = st.selectbox(
        "Результаты поиска",
        options=[m["name"] for m in matches],
        label_visibility="collapsed",
        key="monster_result_select",
    )
    monster = get_monster_by_name(monsters, selected_name)
    if not monster:
        return

    preview_left, preview_right = st.columns([1.1, 1.4])
    with preview_left:
        st.markdown(f"**{monster['name']}**")
        st.caption(monster["meta"])
        st.markdown(f"Класс брони: **{monster['armor_class_value']}**")
        st.markdown(f"Хиты: **{monster['hit_points_value']}**")
    with preview_right:
        if monster["img_url"]:
            st.image(monster["img_url"], width=180)

    with st.form("add_monster_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            custom_name = st.text_input("Имя в бою", value=monster["name"])
        with c2:
            initiative = st.number_input("Инициатива", value=0, step=1, key="monster_init_input")

        submitted = st.form_submit_button("Добавить монстра", use_container_width=True)

    if submitted:
        st.session_state.create_combatants.append(
            new_combatant(
                name=custom_name or monster["name"],
                combatant_type="monster",
                max_hp=int(monster["hit_points_value"]),
                current_hp=int(monster["hit_points_value"]),
                armor_class=int(monster["armor_class_value"]),
                initiative=int(initiative),
                monster_ref=monster["name"],
            )
        )
        st.session_state.create_combatants = sort_prepare_combatants(st.session_state.create_combatants)
        st.success(f"Монстр добавлен: {custom_name or monster['name']}")


def render_prepare_summary(combatants: List[Dict[str, Any]]) -> None:
    summary = get_roster_summary(combatants)
    st.caption(f"Игроков: {summary['players']} | NPC: {summary['npcs']} | Монстров: {summary['monsters']}")


def render_prepare_roster() -> None:
    st.markdown("<div class='section-title'>Текущий состав столкновения</div>", unsafe_allow_html=True)

    combatants = st.session_state.create_combatants
    if not combatants:
        st.info("Состав пока пуст. Добавь участников слева или импортируй JSON.")
        return

    render_prepare_summary(combatants)

    for idx, combatant in enumerate(combatants):
        border = COMBATANT_TYPE_BORDER.get(combatant["type"], "rgba(255,255,255,0.14)")
        with st.container(border=True):
            stripe_col, content_col = st.columns([0.02, 0.98], gap="small")
            with stripe_col:
                st.markdown(
                    f"<div style='background:{border}; width:100%; min-height:80px; border-radius:10px;'></div>",
                    unsafe_allow_html=True,
                )
            with content_col:
                row = st.columns([0.4, 2.0, 1.55, 0.7], gap="small")
                with row[0]:
                    st.markdown(f"**{idx + 1}**")
                with row[1]:
                    st.markdown(f"**{combatant['name']}**")
                    st.markdown(
                        f"<span class='type-chip'>{COMBATANT_TYPE_LABELS[combatant['type']]}</span>",
                        unsafe_allow_html=True,
                    )
                with row[2]:
                    st.markdown(
                        f"<span style='font-size:1.01rem; font-weight:600;'>🛡️ {combatant['armor_class']} &nbsp;&nbsp; ⚡ {combatant['initiative']} &nbsp;&nbsp; ❤️ {combatant['current_hp']}/{combatant['max_hp']}</span>",
                        unsafe_allow_html=True,
                    )
                with row[3]:
                    if st.button("🗑️", key=f"remove_prepare_{combatant['id']}", use_container_width=True):
                        st.session_state.create_combatants = [c for c in combatants if c["id"] != combatant["id"]]
                        st.session_state.create_combatants = sort_prepare_combatants(st.session_state.create_combatants)
                        st.rerun()

    st.markdown("---")
    export_cols = st.columns([1, 1, 1])
    with export_cols[0]:
        party_export = build_party_export(st.session_state.create_combatants)
        st.download_button(
            "Экспорт отряда",
            data=json.dumps(party_export, ensure_ascii=False, indent=2),
            file_name="party.json",
            mime="application/json",
            use_container_width=True,
            key="export_party_bottom",
        )
    with export_cols[1]:
        encounter_export = build_encounter_export(
            st.session_state.encounter_name_input,
            st.session_state.create_combatants,
        )
        st.download_button(
            "Экспорт столкновения",
            data=json.dumps(encounter_export, ensure_ascii=False, indent=2),
            file_name="encounter.json",
            mime="application/json",
            use_container_width=True,
            key="export_encounter_bottom",
        )
    with export_cols[2]:
        if st.button("Очистить состав", key="clear_prepare_roster_bottom", use_container_width=True):
            st.session_state.create_combatants = []
            st.rerun()


def render_prepare_screen(monsters: List[Dict[str, Any]]) -> None:
    render_prepare_action_bar()
    render_json_imports()

    left, right = st.columns([1.05, 0.95], gap="large")

    with left:
        with st.container(border=True):
            tabs = st.tabs(["Игрок / NPC", "Монстр"])
            with tabs[0]:
                render_add_manual_combatant_tab()
            with tabs[1]:
                render_add_monster_tab(monsters)

    with right:
        with st.container(border=True):
            render_prepare_roster()


# ============================================================
# Monster modal
# ============================================================

def render_monster_modal(monsters: List[Dict[str, Any]]) -> None:
    if not st.session_state.get("show_monster_modal", False):
        return

    selected_name = st.session_state.get("selected_monster_name")
    if not selected_name:
        return

    monster = get_monster_by_name(monsters, selected_name)
    if not monster:
        st.session_state.show_monster_modal = False
        return

    @st.dialog(f"Монстр: {monster['name']}", width="large")
    def monster_dialog() -> None:
        left, right = st.columns([1.7, 1.0], gap="large")

        with left:
            st.caption(monster["meta"])
            st.markdown(f"**Класс брони:** {monster['armor_class_raw']}")
            st.markdown(f"**Хиты:** {monster['hit_points_raw']}")
            st.markdown(f"**Скорость:** {monster['speed']}")

            st.markdown("### Характеристики")
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**STR** {monster['str']} {monster['str_mod']}")
            c2.markdown(f"**DEX** {monster['dex']} {monster['dex_mod']}")
            c3.markdown(f"**CON** {monster['con']} {monster['con_mod']}")
            c4, c5, c6 = st.columns(3)
            c4.markdown(f"**INT** {monster['int']} {monster['int_mod']}")
            c5.markdown(f"**WIS** {monster['wis']} {monster['wis_mod']}")
            c6.markdown(f"**CHA** {monster['cha']} {monster['cha_mod']}")

            st.markdown(f"**Спасброски:** {monster['saving_throws']}")
            st.markdown(f"**Навыки:** {monster['skills']}")
            st.markdown(f"**Чувства:** {monster['senses']}")
            st.markdown(f"**Языки:** {monster['languages']}")
            st.markdown(f"**Опасность:** {monster['challenge']}")

            if monster["traits"]:
                st.markdown("### Особенности")
                st.markdown(monster["traits"], unsafe_allow_html=True)
            if monster["actions"]:
                st.markdown("### Действия")
                st.markdown(monster["actions"], unsafe_allow_html=True)
            if monster["legendary_actions"]:
                st.markdown("### Легендарные действия")
                st.markdown(monster["legendary_actions"], unsafe_allow_html=True)

        with right:
            if monster["img_url"]:
                st.image(monster["img_url"], use_container_width=True)

        if st.button("Закрыть", use_container_width=True, key="close_monster_dialog"):
            close_monster_modal()
            st.rerun()

    monster_dialog()


# ============================================================
# Battle screen
# ============================================================

def render_battle_header() -> None:
    battle_state = st.session_state.battle_state
    if not battle_state:
        st.warning("Нет активного боя")
        return

    active = get_active_combatant(battle_state)
    current_turn = battle_state["turn_index"] + 1 if battle_state["combatants"] else 0
    active_name = active["name"] if active else "—"

    with st.container(border=True):
        cols = st.columns([2.3, 1.2, 0.8, 0.8, 1.0, 1.1], gap="small")
        with cols[0]:
            st.markdown(f"**{battle_state['encounter_name']}**")
        with cols[1]:
            st.caption(f"Сейчас: {active_name}")
        with cols[2]:
            st.markdown(f"**Раунд {battle_state['round']}**")
        with cols[3]:
            st.markdown(f"**Ход {current_turn}**")
        with cols[4]:
            if st.button("Следующий", use_container_width=True, type="primary", key="battle_next_turn"):
                next_turn()
                st.rerun()
        with cols[5]:
            if st.button("Завершить бой", use_container_width=True, key="battle_end"):
                st.session_state.battle_state = None
                st.session_state.selected_monster_name = None
                st.session_state.show_monster_modal = False
                st.session_state.screen = "prepare"
                st.rerun()


def render_status_editor(combatant: Dict[str, Any]) -> None:
    new_initiative = st.number_input(
        "Инициатива",
        value=int(combatant["initiative"]),
        step=1,
        key=f"edit_battle_init_{combatant['id']}",
    )
    selected_statuses = st.multiselect(
        "",
        options=list(STATUS_LIBRARY.keys()),
        default=combatant.get("statuses", []),
        key=f"status_editor_{combatant['id']}",
        label_visibility="collapsed",
    )
    if st.button("Применить", key=f"apply_statuses_{combatant['id']}", use_container_width=True):
        update_combatant_initiative(combatant["id"], int(new_initiative))
        update_combatant_statuses(combatant["id"], selected_statuses)
        st.rerun()


def render_combatant_card(combatant: Dict[str, Any], index: int, is_active: bool) -> None:
    normalize_combatant_hp_and_statuses(combatant)

    border = COMBATANT_TYPE_BORDER.get(combatant["type"], "rgba(255,255,255,0.14)")
    is_disabled = combatant["current_hp"] <= 0
    opacity = 0.62 if is_disabled else 1.0
    statuses = combatant.get("statuses", [])

    with st.container(border=True):
        stripe_col, content_col = st.columns([0.018, 0.982], gap="small")

        with stripe_col:
            accent_style = f"background:{border}; width:100%; min-height:54px; border-radius:8px; opacity:{opacity};"
            if is_active:
                accent_style = (
                    f"background:linear-gradient(180deg, rgba(250,204,21,0.95), {border}); "
                    f"width:100%; min-height:54px; border-radius:8px;"
                )
            st.markdown(f"<div style='{accent_style}'></div>", unsafe_allow_html=True)

        with content_col:
            row = st.columns([1.8, 1.3, 1.0, 0.95], gap="small")

            with row[0]:
                name_cols = st.columns([0.18, 1.62, 0.5], gap="small")
                with name_cols[0]:
                    st.markdown(f"**{index + 1}**")
                with name_cols[1]:
                    if combatant["type"] == "monster":
                        if st.button(combatant["name"], key=f"open_monster_{combatant['id']}", use_container_width=True):
                            open_monster_modal(combatant.get("monster_ref") or combatant["name"])
                            st.rerun()
                    else:
                        st.markdown(f"**{combatant['name']}**")
                with name_cols[2]:
                    if is_active:
                        st.markdown("<span class='turn-chip'>ХОД</span>", unsafe_allow_html=True)

            with row[1]:
                st.markdown(
                    f"<span style='font-size:1.04rem; font-weight:600;'>🛡️ {combatant['armor_class']} &nbsp;&nbsp; ⚡ {combatant['initiative']} &nbsp;&nbsp; ❤️ {combatant['current_hp']}/{combatant['max_hp']}</span>",
                    unsafe_allow_html=True,
                )

            with row[2]:
                action_cols = st.columns([1.0, 0.5, 0.5], gap="small")
                hp_delta = action_cols[0].number_input(
                    "",
                    value=0,
                    step=1,
                    key=f"hp_delta_{combatant['id']}",
                    label_visibility="collapsed",
                )
                if action_cols[1].button("➖", key=f"damage_{combatant['id']}", use_container_width=True):
                    apply_hp_delta(combatant["id"], -abs(int(hp_delta)))
                    st.rerun()
                if action_cols[2].button("➕", key=f"heal_{combatant['id']}", use_container_width=True):
                    apply_hp_delta(combatant["id"], abs(int(hp_delta)))
                    st.rerun()

            with row[3]:
                with st.expander("Ред."):
                    render_status_editor(combatant)

            if statuses:
                render_status_chips(statuses)


def render_battle_screen(monsters: List[Dict[str, Any]]) -> None:
    render_battle_header()
    render_monster_modal(monsters)

    battle_state = st.session_state.battle_state
    if not battle_state or not battle_state["combatants"]:
        st.info("Нет участников в текущем бою")
        return

    active = get_active_combatant(battle_state)
    active_id = active["id"] if active else None

    for index, combatant in enumerate(battle_state["combatants"]):
        render_combatant_card(combatant, index, combatant["id"] == active_id)


# ============================================================
# Main
# ============================================================

def main() -> None:
    inject_styles()

    if not st.session_state.is_authenticated:
        render_login()
        return

    header_bar()
    render_sidebar()

    monsters = load_monster_database(st.session_state.selected_db_title)

    if st.session_state.screen == "battle" and st.session_state.battle_state:
        render_battle_screen(monsters)
    else:
        render_prepare_screen(monsters)


if __name__ == "__main__":
    main()
