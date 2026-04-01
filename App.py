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
ENCOUNTERS_FILE = DATA_DIR / "encounters.json"
PRESETS_FILE = DATA_DIR / "presets.json"

MONSTER_DATABASES = {
    "Базовая база монстров": "monsters_base.json",
    "Кастомная база монстров": "monsters_custom.json",
}

STATUS_LIBRARY = {
    "Ослеплён": "Существо не видит и автоматически проваливает проверки, основанные на зрении. Атаки по нему имеют преимущество, его атаки — с помехой.",
    "Очарован": "Существо не может атаковать очаровавшего и не может делать против него вредоносные действия или эффекты.",
    "Оглох": "Существо не слышит и автоматически проваливает проверки, основанные на слухе.",
    "Испуган": "Существо совершает проверки характеристик и атаки с помехой, пока источник страха в пределах видимости.",
    "Схвачен": "Скорость существа становится 0 и не получает бонусов к скорости.",
    "Недееспособен": "Существо не может совершать действия или реакции.",
    "Невидимый": "Существо невозможно увидеть без магии или особого чувства. Атаки по нему с помехой, его атаки с преимуществом.",
    "Парализован": "Существо недееспособно, не может двигаться или говорить. Проваливает спасброски Силы и Ловкости.",
    "Окаменён": "Существо превращено в твёрдую неподвижную субстанцию. Оно недееспособно и не осознаёт происходящее.",
    "Отравлен": "Существо совершает броски атаки и проверки характеристик с помехой.",
    "Сбит с ног": "Единственный вариант перемещения — ползти, пока не встанет.",
    "Скован": "Скорость 0, атаки по существу с преимуществом, его атаки с помехой, помеха на спасброски Ловкости.",
    "Оглушён": "Существо недееспособно, не может двигаться, говорит запинаясь. Автопровал спасбросков Силы и Ловкости.",
    "Без сознания": "Существо недееспособно, не может двигаться или говорить, не осознаёт происходящее, роняет всё, падает ничком.",
    "Мёртв": "Существо мертво и исключается из очереди ходов, если это монстр.",
}

COMBATANT_TYPE_LABELS = {
    "player": "Игрок",
    "npc": "NPC",
    "monster": "Монстр",
}

COMBATANT_TYPE_COLORS = {
    "player": "rgba(59, 130, 246, 0.12)",
    "npc": "rgba(148, 163, 184, 0.12)",
    "monster": "rgba(239, 68, 68, 0.12)",
}

COMBATANT_TYPE_BORDER = {
    "player": "rgba(96, 165, 250, 0.35)",
    "npc": "rgba(148, 163, 184, 0.35)",
    "monster": "rgba(248, 113, 113, 0.35)",
}

# ============================================================
# Setup
# ============================================================


def ensure_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    MONSTERS_DIR.mkdir(exist_ok=True)

    defaults = {
        USERS_FILE: [{"username": "admin", "password": "admin"}],
        ENCOUNTERS_FILE: [],
        PRESETS_FILE: [],
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
        "source": raw,
    }



def load_monster_database(db_title: str) -> List[Dict[str, Any]]:
    file_name = MONSTER_DATABASES[db_title]
    raw_monsters = load_json(MONSTERS_DIR / file_name, [])
    normalized = [normalize_monster(m) for m in raw_monsters if isinstance(m, dict)]
    normalized.sort(key=lambda x: x["name"].lower())
    return normalized


# ============================================================
# State
# ============================================================


def init_state() -> None:
    defaults = {
        "is_authenticated": False,
        "auth_user": None,
        "screen": "prepare",
        "selected_db_title": list(MONSTER_DATABASES.keys())[0],
        "create_combatants": [],
        "battle_state": None,
        "selected_monster_sidebar": None,
        "battle_edit_order_mode": False,
        "encounter_name_input": "",
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



def sort_combatants(combatants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    combatants = assign_sort_order(combatants)
    return sorted(combatants, key=lambda c: (-int(c["initiative"]), int(c["sort_order"])))



def build_encounter_payload(name: str, combatants: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "combatants": clone_combatants_with_new_ids(combatants),
        "created_at": datetime.utcnow().isoformat(),
    }



def build_battle_state(encounter: Dict[str, Any]) -> Dict[str, Any]:
    combatants = sort_combatants(clone_combatants_with_new_ids(encounter["combatants"]))
    for combatant in combatants:
        normalize_combatant_hp_and_statuses(combatant)
    return {
        "encounter_id": encounter["id"],
        "encounter_name": encounter["name"],
        "combatants": combatants,
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
        st.caption("MVP-авторизация на локальном JSON. Перед публикацией замени хранение паролей на безопасное.")
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
# Storage
# ============================================================


def get_encounters() -> List[Dict[str, Any]]:
    return load_json(ENCOUNTERS_FILE, [])



def save_encounters(encounters: List[Dict[str, Any]]) -> None:
    save_json(ENCOUNTERS_FILE, encounters)



def get_presets() -> List[Dict[str, Any]]:
    return load_json(PRESETS_FILE, [])



def save_presets(presets: List[Dict[str, Any]]) -> None:
    save_json(PRESETS_FILE, presets)



def add_encounter(encounter: Dict[str, Any]) -> None:
    encounters = get_encounters()
    encounters.append(encounter)
    save_encounters(encounters)



def update_encounter_name(encounter_id: str, new_name: str) -> None:
    encounters = get_encounters()
    for encounter in encounters:
        if encounter["id"] == encounter_id:
            encounter["name"] = new_name.strip()
            break
    save_encounters(encounters)



def duplicate_encounter(encounter_id: str) -> None:
    encounters = get_encounters()
    for encounter in encounters:
        if encounter["id"] == encounter_id:
            duplicate = deepcopy(encounter)
            duplicate["id"] = str(uuid.uuid4())
            duplicate["name"] = f"{encounter['name']} (копия)"
            duplicate["created_at"] = datetime.utcnow().isoformat()
            duplicate["combatants"] = clone_combatants_with_new_ids(duplicate.get("combatants", []))
            encounters.append(duplicate)
            break
    save_encounters(encounters)



def delete_encounter(encounter_id: str) -> None:
    save_encounters([e for e in get_encounters() if e["id"] != encounter_id])



def add_preset(name: str, combatants: List[Dict[str, Any]]) -> None:
    presets = get_presets()
    presets.append(
        {
            "id": str(uuid.uuid4()),
            "name": name.strip(),
            "characters": clone_combatants_with_new_ids(combatants),
            "created_at": datetime.utcnow().isoformat(),
        }
    )
    save_presets(presets)



def delete_preset(preset_id: str) -> None:
    save_presets([p for p in get_presets() if p["id"] != preset_id])



def duplicate_preset(preset_id: str) -> None:
    presets = get_presets()
    for preset in presets:
        if preset["id"] == preset_id:
            duplicate = deepcopy(preset)
            duplicate["id"] = str(uuid.uuid4())
            duplicate["name"] = f"{preset['name']} (копия)"
            duplicate["created_at"] = datetime.utcnow().isoformat()
            duplicate["characters"] = clone_combatants_with_new_ids(duplicate.get("characters", []))
            presets.append(duplicate)
            break
    save_presets(presets)



def rename_preset(preset_id: str, new_name: str) -> None:
    presets = get_presets()
    for preset in presets:
        if preset["id"] == preset_id:
            preset["name"] = new_name.strip()
            break
    save_presets(presets)


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



def update_combatant_initiative(combatant_id: str, new_initiative: int) -> None:
    battle_state = st.session_state.battle_state
    if not battle_state:
        return

    active = get_active_combatant(battle_state)
    active_id = active["id"] if active else None

    for combatant in battle_state["combatants"]:
        if combatant["id"] == combatant_id:
            combatant["initiative"] = int(new_initiative)
            break

    battle_state["combatants"] = sort_combatants(battle_state["combatants"])

    if active_id:
        for idx, combatant in enumerate(battle_state["combatants"]):
            if combatant["id"] == active_id:
                battle_state["turn_index"] = idx
                break



def move_combatant(combatant_id: str, direction: str) -> None:
    battle_state = st.session_state.battle_state
    if not battle_state:
        return

    combatants = battle_state["combatants"]
    active = get_active_combatant(battle_state)
    active_id = active["id"] if active else None

    index = next((i for i, c in enumerate(combatants) if c["id"] == combatant_id), None)
    if index is None:
        return

    target_index = index - 1 if direction == "up" else index + 1
    if target_index < 0 or target_index >= len(combatants):
        return

    combatants[index], combatants[target_index] = combatants[target_index], combatants[index]
    assign_sort_order(combatants)

    if active_id:
        for idx, combatant in enumerate(combatants):
            if combatant["id"] == active_id:
                battle_state["turn_index"] = idx
                break


# ============================================================
# UI helpers
# ============================================================


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0.9rem;
            padding-bottom: 1.6rem;
            max-width: 1800px;
        }
        .hero-card,
        .battle-hero,
        .encounter-row,
        .combat-card,
        .library-card {
            border: 1px solid rgba(255,255,255,0.08);
            background: rgba(255,255,255,0.03);
            border-radius: 18px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.22);
        }
        .hero-card { padding: 24px; margin-top: 8vh; }
        .battle-hero { padding: 18px; margin-bottom: 14px; }
        .encounter-row { padding: 12px 14px; margin-bottom: 10px; }
        .combat-card {
            padding: 12px 14px;
            margin-bottom: 10px;
            position: relative;
            overflow: hidden;
        }
        .encounter-row {
        padding: 12px 14px;
        margin-bottom: 10px;
        border-left: 6px solid var(--accent-color, rgba(255,255,255,0.2));
        }
        .combat-card {
           padding: 12px 14px;
           margin-bottom: 10px;
           position: relative;
           overflow: hidden;
           border-left: 6px solid var(--accent-color, rgba(255,255,255,0.2));
}
        .type-chip,
        .status-chip,
        .turn-chip {
            display: inline-block;
            border-radius: 999px;
            padding: 4px 10px;
            margin-right: 6px;
            margin-top: 4px;
            font-size: 0.8rem;
            font-weight: 600;
            border: 1px solid rgba(255,255,255,0.08);
            background: rgba(255,255,255,0.06);
        }
        .turn-chip {
            background: rgba(250, 204, 21, 0.18);
            border-color: rgba(250, 204, 21, 0.35);
        }
        .metric-chip {
            display: inline-block;
            border-radius: 12px;
            padding: 6px 10px;
            margin-right: 8px;
            margin-bottom: 6px;
            font-size: 0.95rem;
            font-weight: 600;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
        }
        .small-gap { height: 0.35rem; }
        .section-title {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.65rem;
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
    left, right = st.columns([1.8, 0.7])
    with left:
        st.title(APP_TITLE)
    with right:
        st.markdown("### ")
        st.caption(f"Пользователь: {st.session_state.auth_user}")
        if st.button("Выйти", use_container_width=True):
            st.session_state.is_authenticated = False
            st.session_state.auth_user = None
            st.session_state.screen = "prepare"
            st.session_state.battle_state = None
            st.session_state.selected_monster_sidebar = None
            st.rerun()



def combatant_type_badge(combatant_type: str) -> str:
    return COMBATANT_TYPE_LABELS.get(combatant_type, combatant_type)



def get_monster_by_name(monsters: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    for monster in monsters:
        if monster["name"] == name:
            return monster
    return None



def render_status_help() -> None:
    with st.expander("Подсказка по статусам"):
        for status, description in STATUS_LIBRARY.items():
            st.markdown(f"**{status}** — {description}")



def render_status_chips(statuses: List[str], empty_text: str = "Нет статусов") -> None:
    if not statuses:
        st.caption(empty_text)
        return
    html = "".join([f"<span class='status-chip'>{status}</span>" for status in statuses])
    st.markdown(html, unsafe_allow_html=True)



def hp_ratio(current_hp: int, max_hp: int) -> float:
    if max_hp <= 0:
        return 0.0
    return max(0.0, min(1.0, current_hp / max_hp))



def render_hp_bar(current_hp: int, max_hp: int) -> None:
    ratio = hp_ratio(current_hp, max_hp)
    st.progress(ratio, text=f"❤️ {current_hp} / {max_hp}")



def render_monster_sidebar(monsters: List[Dict[str, Any]]) -> None:
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
        st.header("Карточка монстра")
        selected_name = st.session_state.selected_monster_sidebar
        if not selected_name:
            st.info("Кликни по имени монстра в бою, чтобы открыть его карточку.")
            return

        monster = get_monster_by_name(monsters, selected_name)
        if not monster:
            st.warning("Монстр не найден в выбранной базе.")
            return

        st.subheader(monster["name"])
        if monster["img_url"]:
            st.image(monster["img_url"], use_container_width=True)
        st.caption(monster["meta"])
        st.markdown(f"**Класс брони:** {monster['armor_class_raw']}")
        st.markdown(f"**Хиты:** {monster['hit_points_raw']}")
        st.markdown(f"**Скорость:** {monster['speed']}")

        st.markdown("### Характеристики")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**STR**  {monster['str']} {monster['str_mod']}")
        c2.markdown(f"**DEX**  {monster['dex']} {monster['dex_mod']}")
        c3.markdown(f"**CON**  {monster['con']} {monster['con_mod']}")
        c4, c5, c6 = st.columns(3)
        c4.markdown(f"**INT**  {monster['int']} {monster['int_mod']}")
        c5.markdown(f"**WIS**  {monster['wis']} {monster['wis_mod']}")
        c6.markdown(f"**CHA**  {monster['cha']} {monster['cha_mod']}")

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


# ============================================================
# Create screen
# ============================================================


def render_prepare_action_bar() -> None:
    st.subheader("Подготовка столкновения")
    c1, c2, c3, c4, c5 = st.columns([1.4, 1.2, 1.0, 1.0, 1.0])
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
        st.markdown("<div class='small-gap'></div>", unsafe_allow_html=True)
        if st.button("Сохранить столкновение", use_container_width=True):
            if not st.session_state.encounter_name_input.strip():
                st.error("Укажи название столкновения")
            elif not st.session_state.create_combatants:
                st.error("Добавь хотя бы одного участника")
            else:
                payload = build_encounter_payload(
                    st.session_state.encounter_name_input,
                    st.session_state.create_combatants,
                )
                add_encounter(payload)
                st.success("Столкновение сохранено")
    with c4:
        st.markdown("<div class='small-gap'></div>", unsafe_allow_html=True)
        if st.button("Начать бой", use_container_width=True, type="primary"):
            if not st.session_state.create_combatants:
                st.error("Сначала добавь участников")
            else:
                temp_encounter = build_encounter_payload(
                    st.session_state.encounter_name_input.strip() or "Несохранённое столкновение",
                    st.session_state.create_combatants,
                )
                st.session_state.battle_state = build_battle_state(temp_encounter)
                st.session_state.screen = "battle"
                st.rerun()
    with c5:
        st.markdown("<div class='small-gap'></div>", unsafe_allow_html=True)
        if st.button("Очистить состав", use_container_width=True):
            st.session_state.create_combatants = []
            st.rerun()



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
        combatant = new_combatant(
            name=name,
            combatant_type=combatant_type,
            max_hp=int(max_hp),
            current_hp=int(min(current_hp, max_hp)),
            armor_class=int(armor_class),
            initiative=int(initiative),
        )
        st.session_state.create_combatants.append(combatant)
        st.session_state.create_combatants = sort_combatants(st.session_state.create_combatants)
        st.success(f"Добавлен: {name}")



def render_add_monster_tab(monsters: List[Dict[str, Any]]) -> None:
    search = st.text_input("Поиск по имени монстра", placeholder="Например, Aboleth")
    filtered = monsters
    if search.strip():
        q = search.strip().lower()
        filtered = [m for m in monsters if q in m["name"].lower()]

    options = [m["name"] for m in filtered[:200]]
    selected_name = st.selectbox("Выбери монстра", options=options if options else [""], index=0)
    monster = get_monster_by_name(monsters, selected_name) if selected_name else None

    if not monster:
        st.info("Выбери монстра из списка")
        return

    preview_left, preview_right = st.columns([1.1, 1.4])
    with preview_left:
        st.markdown("**Предпросмотр**")
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
            initiative = st.number_input("Инициатива", value=0, step=1, key="monster_init_input")
        with c2:
            use_edit_mode = st.checkbox("Изменить параметры перед добавлением")
            edit_ac = monster["armor_class_value"]
            edit_hp = monster["hit_points_value"]
            if use_edit_mode:
                edit_ac = st.number_input("Класс брони (override)", min_value=0, value=monster["armor_class_value"], step=1)
                edit_hp = st.number_input("HP (override)", min_value=1, value=monster["hit_points_value"], step=1)

        submitted = st.form_submit_button("Добавить монстра", use_container_width=True)

    if submitted:
        combatant = new_combatant(
            name=custom_name or monster["name"],
            combatant_type="monster",
            max_hp=int(edit_hp),
            current_hp=int(edit_hp),
            armor_class=int(edit_ac),
            initiative=int(initiative),
            monster_ref=monster["name"],
        )
        st.session_state.create_combatants.append(combatant)
        st.session_state.create_combatants = sort_combatants(st.session_state.create_combatants)
        st.success(f"Монстр добавлен: {combatant['name']}")



def render_presets_tab() -> None:
    presets = get_presets()

    st.markdown("**Сохранить новый пресет**")
    p1, p2 = st.columns([1.2, 1.1])
    with p1:
        preset_name = st.text_input("Название пресета", key="new_preset_name")
    with p2:
        save_scope = st.radio(
            "Что сохранить",
            options=["Текущий состав", "Только игроки и NPC"],
            horizontal=True,
        )
    if st.button("Сохранить как пресет", use_container_width=True):
        roster = st.session_state.create_combatants
        if save_scope == "Только игроки и NPC":
            roster = [c for c in roster if c["type"] in {"player", "npc"}]
        if not preset_name.strip():
            st.error("Укажи название пресета")
        elif not roster:
            st.error("Нет участников для сохранения")
        else:
            add_preset(preset_name, roster)
            st.success("Пресет сохранён")
            st.rerun()

    st.markdown("---")
    st.markdown("**Список пресетов**")
    if not presets:
        st.info("Пока нет сохранённых пресетов")
        return

    for preset in presets:
        with st.container(border=True):
            st.markdown(f"**{preset['name']}**")
            st.caption(f"Участников: {len(preset.get('characters', []))}")
            b1, b2, b3 = st.columns([1.0, 1.0, 1.0])
            if b1.button("Загрузить", key=f"load_preset_{preset['id']}", use_container_width=True):
                st.session_state.create_combatants.extend(
                    clone_combatants_with_new_ids(preset.get("characters", []))
                )
                st.session_state.create_combatants = sort_combatants(st.session_state.create_combatants)
                st.rerun()
            if b2.button("Дублировать", key=f"dup_preset_{preset['id']}", use_container_width=True):
                duplicate_preset(preset["id"])
                st.rerun()
            if b3.button("Удалить", key=f"del_preset_{preset['id']}", use_container_width=True):
                delete_preset(preset["id"])
                st.rerun()

            rn1, rn2 = st.columns([2.2, 1.0])
            new_name = rn1.text_input(
                "Новое имя",
                value=preset["name"],
                key=f"preset_name_input_{preset['id']}",
                label_visibility="collapsed",
            )
            if rn2.button("Переименовать", key=f"rename_preset_{preset['id']}", use_container_width=True):
                rename_preset(preset["id"], new_name)
                st.rerun()

            st.download_button(
                "Скачать JSON",
                data=json.dumps(preset, ensure_ascii=False, indent=2),
                file_name=f"preset_{preset['name']}.json",
                mime="application/json",
                key=f"download_preset_{preset['id']}",
                use_container_width=True,
            )



def render_prepare_roster() -> None:
    st.markdown("<div class='section-title'>Текущий состав столкновения</div>", unsafe_allow_html=True)
    combatants = st.session_state.create_combatants
    if not combatants:
        st.info("Список пуст. Добавь игроков, NPC или монстров.")
        return

    for idx, combatant in enumerate(combatants):
        bg = COMBATANT_TYPE_COLORS.get(combatant["type"], "rgba(255,255,255,0.04)")
        border = COMBATANT_TYPE_BORDER.get(combatant["type"], "rgba(255,255,255,0.14)")
        st.markdown(
            f"<div class='encounter-row' style='background:{bg}; border-color:{border}; --accent-color:{border};'>",
            unsafe_allow_html=True,
        )
        c1, c2, c3, c4 = st.columns([0.45, 2.0, 1.7, 0.9])
        with c1:
            st.markdown(f"### {idx + 1}")
        with c2:
            st.markdown(f"**{combatant['name']}**")
            st.markdown(f"<span class='type-chip'>{combatant_type_badge(combatant['type'])}</span>", unsafe_allow_html=True)
        with c3:
            metric_html = (
                f"<span class='metric-chip'>🛡️ {combatant['armor_class']}</span>"
                f"<span class='metric-chip'>⚡ {combatant['initiative']}</span>"
                f"<span class='metric-chip'>❤️ {combatant['current_hp']} / {combatant['max_hp']}</span>"
            )
            st.markdown(metric_html, unsafe_allow_html=True)
        with c4:
            if st.button("Удалить", key=f"remove_create_{combatant['id']}", use_container_width=True):
                st.session_state.create_combatants = [c for c in combatants if c["id"] != combatant["id"]]
                st.session_state.create_combatants = sort_combatants(st.session_state.create_combatants)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)



def render_saved_encounters_block() -> None:
    st.markdown("<div class='section-title'>Сохранённые столкновения</div>", unsafe_allow_html=True)
    encounters = get_encounters()
    if not encounters:
        st.info("Сохранённых столкновений пока нет")
        return

    for encounter in encounters:
        with st.container(border=True):
            st.markdown(f"**{encounter['name']}**")
            st.caption(f"Участников: {len(encounter.get('combatants', []))}")
            a1, a2, a3 = st.columns([1.1, 1.0, 1.0])
            if a1.button("Запустить бой", key=f"start_enc_{encounter['id']}", use_container_width=True):
                st.session_state.battle_state = build_battle_state(encounter)
                st.session_state.screen = "battle"
                st.rerun()
            if a2.button("Дублировать", key=f"dup_enc_{encounter['id']}", use_container_width=True):
                duplicate_encounter(encounter["id"])
                st.rerun()
            if a3.button("Удалить", key=f"del_enc_{encounter['id']}", use_container_width=True):
                delete_encounter(encounter["id"])
                st.rerun()

            r1, r2 = st.columns([2.2, 1.0])
            new_name = r1.text_input(
                "Новое имя столкновения",
                value=encounter["name"],
                key=f"enc_name_input_{encounter['id']}",
                label_visibility="collapsed",
            )
            if r2.button("Переименовать", key=f"rename_enc_{encounter['id']}", use_container_width=True):
                update_encounter_name(encounter["id"], new_name)
                st.rerun()



def render_prepare_screen(monsters: List[Dict[str, Any]]) -> None:
    render_prepare_action_bar()

    left, right = st.columns([1.1, 0.9], gap="large")

    with left:
        with st.container(border=True):
            tabs = st.tabs(["Игрок / NPC", "Монстр", "Пресеты"])
            with tabs[0]:
                render_add_manual_combatant_tab()
            with tabs[1]:
                render_add_monster_tab(monsters)
            with tabs[2]:
                render_presets_tab()

    with right:
        with st.container(border=True):
            render_prepare_roster()
            c1, c2 = st.columns(2)
            if c1.button("Очистить состав", key="clear_prepare_roster_secondary", use_container_width=True):
                st.session_state.create_combatants = []
                st.rerun()
            if c2.button("Начать бой", key="start_battle_secondary", use_container_width=True, type="primary"):
                if not st.session_state.create_combatants:
                    st.error("Сначала добавь участников")
                else:
                    temp_encounter = build_encounter_payload(
                        st.session_state.encounter_name_input.strip() or "Несохранённое столкновение",
                        st.session_state.create_combatants,
                    )
                    st.session_state.battle_state = build_battle_state(temp_encounter)
                    st.session_state.screen = "battle"
                    st.rerun()

    st.markdown("---")
    with st.container(border=True):
        render_saved_encounters_block()


# ============================================================
# Battle screen
# ============================================================


def render_battle_header() -> None:
    battle_state = st.session_state.battle_state
    if not battle_state:
        st.warning("Нет активного боя")
        return

    active = get_active_combatant(battle_state)
    st.markdown("<div class='battle-hero'>", unsafe_allow_html=True)
    st.markdown(f"### {battle_state['encounter_name']}")
    current_turn = battle_state["turn_index"] + 1 if battle_state["combatants"] else 0
    active_name = active["name"] if active else "—"
    st.markdown(f"**Раунд {battle_state['round']} · Ход {current_turn} · Сейчас ходит: {active_name}**")
    st.markdown("</div>", unsafe_allow_html=True)

    b1, b2, b3 = st.columns([1.1, 1.1, 1.0])
    if b1.button("Следующий ход", use_container_width=True, type="primary"):
        next_turn()
        st.rerun()
    if b2.button(
        "Редактировать порядок" if not st.session_state.battle_edit_order_mode else "Завершить редактирование",
        use_container_width=True,
    ):
        st.session_state.battle_edit_order_mode = not st.session_state.battle_edit_order_mode
        st.rerun()
    if b3.button("Завершить бой", use_container_width=True):
        st.session_state.battle_state = None
        st.session_state.selected_monster_sidebar = None
        st.session_state.battle_edit_order_mode = False
        st.session_state.screen = "prepare"
        st.rerun()



def render_status_editor(combatant: Dict[str, Any]) -> None:
    selected_statuses = st.multiselect(
        "Статусы",
        options=list(STATUS_LIBRARY.keys()),
        default=combatant.get("statuses", []),
        help="; ".join([f"{k}: {v}" for k, v in STATUS_LIBRARY.items()]),
        key=f"status_editor_{combatant['id']}",
    )
    if st.button("Применить статусы", key=f"apply_statuses_{combatant['id']}", use_container_width=True):
        update_combatant_statuses(combatant["id"], selected_statuses)
        st.rerun()



def render_order_editor(combatant: Dict[str, Any]) -> None:
    c1, c2, c3 = st.columns([1.2, 1.0, 1.0])
    new_init = c1.number_input(
        "Инициатива",
        value=int(combatant["initiative"]),
        step=1,
        key=f"order_init_{combatant['id']}",
    )
    if c2.button("Вверх", key=f"move_up_{combatant['id']}", use_container_width=True):
        move_combatant(combatant["id"], "up")
        st.rerun()
    if c3.button("Вниз", key=f"move_down_{combatant['id']}", use_container_width=True):
        move_combatant(combatant["id"], "down")
        st.rerun()

    if int(new_init) != int(combatant["initiative"]):
        update_combatant_initiative(combatant["id"], int(new_init))
        st.rerun()



def render_combatant_card(combatant: Dict[str, Any], index: int, is_active: bool) -> None:
    normalize_combatant_hp_and_statuses(combatant)

    bg = COMBATANT_TYPE_COLORS.get(combatant["type"], "rgba(255,255,255,0.04)")
    border = COMBATANT_TYPE_BORDER.get(combatant["type"], "rgba(255,255,255,0.14)")
    active_shadow = "0 0 0 2px rgba(250, 204, 21, 0.55) inset" if is_active else "none"
    is_disabled = combatant["current_hp"] <= 0
    opacity = "0.65" if is_disabled else "1"

    st.markdown(
        f"<div class='combat-card' style='background:{bg}; border-color:{border}; --accent-color:{border}; box-shadow: {active_shadow}, 0 4px 12px rgba(0,0,0,0.22); opacity:{opacity};'>",
        unsafe_allow_html=True,
    )

    info_col, state_col, action_col = st.columns([1.4, 1.8, 1.1], gap="medium")

    with info_col:
        top_left, top_right = st.columns([0.22, 1.78])
        top_left.markdown(f"### {index + 1}")
        with top_right:
            if combatant["type"] == "monster":
                if st.button(combatant["name"], key=f"open_monster_{combatant['id']}", use_container_width=True):
                    st.session_state.selected_monster_sidebar = combatant.get("monster_ref") or combatant["name"]
                    st.rerun()
            else:
                st.markdown(f"**{combatant['name']}**")

            chips = [f"<span class='type-chip'>{combatant_type_badge(combatant['type'])}</span>"]
            if is_active:
                chips.append("<span class='turn-chip'>ХОД</span>")
            st.markdown("".join(chips), unsafe_allow_html=True)

    with state_col:
        metric_html = (
            f"<span class='metric-chip'>🛡️ {combatant['armor_class']}</span>"
            f"<span class='metric-chip'>⚡ {combatant['initiative']}</span>"
            f"<span class='metric-chip'>❤️ {combatant['current_hp']} / {combatant['max_hp']}</span>"
        )
        st.markdown(metric_html, unsafe_allow_html=True)
        render_hp_bar(int(combatant["current_hp"]), int(combatant["max_hp"]))
        status_left, status_right = st.columns([1.35, 1.0])
        with status_left:
            render_status_chips(combatant.get("statuses", []))
        with status_right:
            with st.expander("Статусы"):
                render_status_editor(combatant)

    with action_col:
        hp_delta = st.number_input(
            "Значение изменения HP",
            value=0,
            step=1,
            key=f"hp_delta_{combatant['id']}",
            label_visibility="collapsed",
        )
        st.caption("Изменение HP")
        h1, h2 = st.columns(2)
        if h1.button("- Урон", key=f"damage_{combatant['id']}", use_container_width=True):
            apply_hp_delta(combatant["id"], -abs(int(hp_delta)))
            st.rerun()
        if h2.button("+ Лечение", key=f"heal_{combatant['id']}", use_container_width=True):
            apply_hp_delta(combatant["id"], abs(int(hp_delta)))
            st.rerun()

        if st.session_state.battle_edit_order_mode:
            st.markdown("---")
            st.markdown("**Редактирование порядка**")
            render_order_editor(combatant)

    st.markdown("</div>", unsafe_allow_html=True)



def render_battle_screen(monsters: List[Dict[str, Any]]) -> None:
    st.subheader("Проведение боя")
    render_battle_header()
    render_status_help()

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

    monsters = load_monster_database(st.session_state.selected_db_title)
    render_monster_sidebar(monsters)

    if st.session_state.screen == "battle" and st.session_state.battle_state:
        render_battle_screen(monsters)
    else:
        render_prepare_screen(monsters)


if __name__ == "__main__":
    main()
