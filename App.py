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
    "player": "rgba(59, 130, 246, 0.18)",
    "npc": "rgba(148, 163, 184, 0.18)",
    "monster": "rgba(239, 68, 68, 0.18)",
}

ACTIVE_ROW_OUTLINE = "2px solid rgba(250, 204, 21, 0.95)"

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
        "screen": "create",
        "selected_db_title": list(MONSTER_DATABASES.keys())[0],
        "create_combatants": [],
        "battle_state": None,
        "selected_monster_sidebar": None,
        "edit_mode": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


# ============================================================
# Domain factories
# ============================================================


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
    return sorted(
        combatants,
        key=lambda c: (-int(c["initiative"]), int(c["sort_order"])),
    )



def build_encounter_payload(name: str, combatants: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "combatants": deepcopy(combatants),
        "created_at": datetime.utcnow().isoformat(),
    }



def build_battle_state(encounter: Dict[str, Any]) -> Dict[str, Any]:
    combatants = sort_combatants(deepcopy(encounter["combatants"]))
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
    st.title(APP_TITLE)
    st.subheader("Вход")
    st.caption("MVP-авторизация на локальном JSON. Перед публикацией парольное хранение лучше заменить на безопасное.")

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


# ============================================================
# Storage actions
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
            encounters.append(duplicate)
            break
    save_encounters(encounters)



def delete_encounter(encounter_id: str) -> None:
    encounters = [e for e in get_encounters() if e["id"] != encounter_id]
    save_encounters(encounters)



def add_preset(name: str, combatants: List[Dict[str, Any]]) -> None:
    presets = get_presets()
    presets.append(
        {
            "id": str(uuid.uuid4()),
            "name": name.strip(),
            "characters": deepcopy(combatants),
            "created_at": datetime.utcnow().isoformat(),
        }
    )
    save_presets(presets)



def delete_preset(preset_id: str) -> None:
    presets = [p for p in get_presets() if p["id"] != preset_id]
    save_presets(presets)



def duplicate_preset(preset_id: str) -> None:
    presets = get_presets()
    for preset in presets:
        if preset["id"] == preset_id:
            duplicate = deepcopy(preset)
            duplicate["id"] = str(uuid.uuid4())
            duplicate["name"] = f"{preset['name']} (копия)"
            duplicate["created_at"] = datetime.utcnow().isoformat()
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

    active_id = get_active_combatant(battle_state)["id"] if get_active_combatant(battle_state) else None

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
    active_id = get_active_combatant(battle_state)["id"] if get_active_combatant(battle_state) else None

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
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }
        .app-card {
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 16px;
            background: rgba(255,255,255,0.02);
            margin-bottom: 12px;
        }
        .combat-row {
            border-radius: 16px;
            padding: 10px 12px;
            margin-bottom: 8px;
            border: 1px solid rgba(255,255,255,0.08);
        }
        .combat-name-button button {
            text-align: left !important;
            justify-content: flex-start !important;
            width: 100%;
        }
        .small-muted {
            color: rgba(255,255,255,0.65);
            font-size: 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )



def header_bar() -> None:
    left, right = st.columns([0.75, 0.25])
    with left:
        st.title(APP_TITLE)
    with right:
        st.write("")
        st.write(f"**Пользователь:** {st.session_state.auth_user}")
        if st.button("Выйти", use_container_width=True):
            st.session_state.is_authenticated = False
            st.session_state.auth_user = None
            st.session_state.screen = "create"
            st.session_state.battle_state = None
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



def render_monster_sidebar(monsters: List[Dict[str, Any]]) -> None:
    with st.sidebar:
        st.header("Карточка монстра")
        selected_name = st.session_state.selected_monster_sidebar
        if not selected_name:
            st.info("Нажми на имя монстра в бою, чтобы открыть его карточку.")
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
        cols = st.columns(3)
        cols[0].markdown(f"**STR**  {monster['str']} {monster['str_mod']}")
        cols[1].markdown(f"**DEX**  {monster['dex']} {monster['dex_mod']}")
        cols[2].markdown(f"**CON**  {monster['con']} {monster['con_mod']}")
        cols = st.columns(3)
        cols[0].markdown(f"**INT**  {monster['int']} {monster['int_mod']}")
        cols[1].markdown(f"**WIS**  {monster['wis']} {monster['wis_mod']}")
        cols[2].markdown(f"**CHA**  {monster['cha']} {monster['cha_mod']}")

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


def render_add_manual_combatant() -> None:
    st.markdown("### Добавить игрока / NPC")
    with st.form("add_manual_combatant_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            name = st.text_input("Имя")
            combatant_type = st.selectbox(
                "Тип",
                options=["player", "npc"],
                format_func=lambda x: COMBATANT_TYPE_LABELS[x],
            )
        with col2:
            max_hp = st.number_input("Макс HP", min_value=1, value=10, step=1)
            current_hp = st.number_input("Текущий HP", min_value=0, value=10, step=1)
        with col3:
            armor_class = st.number_input("Класс брони", min_value=0, value=10, step=1)
            initiative = st.number_input("Инициатива", value=0, step=1)

        submitted = st.form_submit_button("Добавить", use_container_width=True)

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



def render_add_monster(monsters: List[Dict[str, Any]]) -> None:
    st.markdown("### Добавить монстра")

    search = st.text_input("Поиск по имени монстра", placeholder="Например, Aboleth")
    filtered = monsters
    if search.strip():
        q = search.strip().lower()
        filtered = [m for m in monsters if q in m["name"].lower()]

    options = [m["name"] for m in filtered[:200]]
    selected_name = st.selectbox("Выбери монстра", options=options if options else [""], index=0)

    monster = get_monster_by_name(monsters, selected_name) if selected_name else None
    if monster:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("AC", monster["armor_class_value"])
        c2.metric("HP", monster["hit_points_value"])
        c3.caption(monster["meta"])
        c4.write("")

        with st.form("add_monster_form", clear_on_submit=True):
            left, mid, right = st.columns(3)
            with left:
                custom_name = st.text_input("Имя в бою", value=monster["name"])
            with mid:
                initiative = st.number_input("Инициатива", value=0, step=1, key="monster_init_input")
            with right:
                use_edit_mode = st.checkbox("Редактировать AC/HP при добавлении")

            edit_ac = monster["armor_class_value"]
            edit_hp = monster["hit_points_value"]
            if use_edit_mode:
                ec1, ec2 = st.columns(2)
                with ec1:
                    edit_ac = st.number_input("AC (override)", min_value=0, value=monster["armor_class_value"], step=1)
                with ec2:
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



def render_create_roster_table() -> None:
    st.markdown("### Участники столкновения")
    combatants = st.session_state.create_combatants
    if not combatants:
        st.info("Список пуст. Добавь игроков, NPC или монстров.")
        return

    for idx, combatant in enumerate(combatants):
        bg = COMBATANT_TYPE_COLORS.get(combatant["type"], "rgba(255,255,255,0.04)")
        st.markdown(
            f"<div class='combat-row' style='background:{bg};'>",
            unsafe_allow_html=True,
        )
        c1, c2, c3, c4, c5, c6, c7 = st.columns([0.5, 2.0, 1.1, 0.9, 1.0, 1.0, 1.2])
        c1.markdown(f"**{idx + 1}.**")
        c2.markdown(f"**{combatant['name']}**")
        c3.markdown(combatant_type_badge(combatant["type"]))
        c4.markdown(f"AC: **{combatant['armor_class']}**")
        c5.markdown(f"HP: **{combatant['current_hp']}/{combatant['max_hp']}**")
        c6.markdown(f"Init: **{combatant['initiative']}**")
        if c7.button("Удалить", key=f"remove_create_{combatant['id']}", use_container_width=True):
            st.session_state.create_combatants = [c for c in combatants if c["id"] != combatant["id"]]
            st.session_state.create_combatants = sort_combatants(st.session_state.create_combatants)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)



def render_presets_block() -> None:
    st.markdown("### Пресеты")
    presets = get_presets()

    left, right = st.columns([1.1, 1.3])
    with left:
        preset_name = st.text_input("Название нового пресета", key="new_preset_name")
        save_scope = st.radio(
            "Что сохранить",
            options=["Текущий состав", "Только игроков и NPC"],
            horizontal=True,
        )
        if st.button("Сохранить как пресет", use_container_width=True):
            roster = st.session_state.create_combatants
            if save_scope == "Только игроков и NPC":
                roster = [c for c in roster if c["type"] in {"player", "npc"}]
            if not preset_name.strip():
                st.error("Укажи название пресета")
            elif not roster:
                st.error("Нет участников для сохранения")
            else:
                add_preset(preset_name, roster)
                st.success("Пресет сохранён")
                st.rerun()

    with right:
        if not presets:
            st.info("Пока нет сохранённых пресетов")
        else:
            for preset in presets:
                with st.container(border=True):
                    st.markdown(f"**{preset['name']}**")
                    st.caption(f"Участников: {len(preset.get('characters', []))}")
                    a, b, c, d, e = st.columns(5)
                    if a.button("Загрузить", key=f"load_preset_{preset['id']}", use_container_width=True):
                        st.session_state.create_combatants.extend(deepcopy(preset.get("characters", [])))
                        st.session_state.create_combatants = sort_combatants(st.session_state.create_combatants)
                        st.success(f"Загружен пресет: {preset['name']}")
                        st.rerun()
                    if b.button("Дубль", key=f"dup_preset_{preset['id']}", use_container_width=True):
                        duplicate_preset(preset["id"])
                        st.rerun()
                    if c.button("JSON", key=f"download_preset_{preset['id']}", use_container_width=True):
                        pass
                    new_name = d.text_input("", value=preset["name"], label_visibility="collapsed", key=f"rename_preset_input_{preset['id']}")
                    if d.button("Переим.", key=f"rename_preset_{preset['id']}", use_container_width=True):
                        rename_preset(preset["id"], new_name)
                        st.rerun()
                    if e.button("Удалить", key=f"delete_preset_{preset['id']}", use_container_width=True):
                        delete_preset(preset["id"])
                        st.rerun()

                    st.download_button(
                        "Скачать JSON",
                        data=json.dumps(preset, ensure_ascii=False, indent=2),
                        file_name=f"preset_{preset['name']}.json",
                        mime="application/json",
                        key=f"download_real_preset_{preset['id']}",
                        use_container_width=True,
                    )



def render_saved_encounters_block() -> None:
    st.markdown("### Сохранённые столкновения")
    encounters = get_encounters()
    if not encounters:
        st.info("Сохранённых столкновений пока нет")
        return

    for encounter in encounters:
        with st.container(border=True):
            st.markdown(f"**{encounter['name']}**")
            st.caption(f"Участников: {len(encounter.get('combatants', []))}")
            c1, c2, c3, c4 = st.columns([1.2, 1.0, 1.5, 1.0])
            if c1.button("Запустить бой", key=f"start_saved_{encounter['id']}", use_container_width=True):
                st.session_state.battle_state = build_battle_state(encounter)
                st.session_state.screen = "battle"
                st.rerun()
            if c2.button("Дублировать", key=f"dup_enc_{encounter['id']}", use_container_width=True):
                duplicate_encounter(encounter["id"])
                st.rerun()
            new_name = c3.text_input("", value=encounter["name"], label_visibility="collapsed", key=f"enc_name_{encounter['id']}")
            if c3.button("Переименовать", key=f"rename_enc_{encounter['id']}", use_container_width=True):
                update_encounter_name(encounter["id"], new_name)
                st.rerun()
            if c4.button("Удалить", key=f"del_enc_{encounter['id']}", use_container_width=True):
                delete_encounter(encounter["id"])
                st.rerun()



def render_create_screen(monsters: List[Dict[str, Any]]) -> None:
    st.subheader("Создание боевого столкновения")

    toolbar_left, toolbar_mid, toolbar_right = st.columns([1.2, 1.2, 1.6])
    with toolbar_left:
        st.session_state.selected_db_title = st.selectbox(
            "База монстров",
            options=list(MONSTER_DATABASES.keys()),
            index=list(MONSTER_DATABASES.keys()).index(st.session_state.selected_db_title),
        )
    with toolbar_mid:
        encounter_name = st.text_input("Название столкновения", key="encounter_name_input")
    with toolbar_right:
        st.write("")
        st.write("")
        save_clicked = st.button("Сохранить столкновение", use_container_width=True)

    if save_clicked:
        if not encounter_name.strip():
            st.error("Укажи название столкновения")
        elif not st.session_state.create_combatants:
            st.error("Добавь хотя бы одного участника")
        else:
            payload = build_encounter_payload(encounter_name, st.session_state.create_combatants)
            add_encounter(payload)
            st.success("Столкновение сохранено")

    left, right = st.columns([1.15, 1.0])
    with left:
        with st.container(border=True):
            render_add_manual_combatant()
        with st.container(border=True):
            render_add_monster(monsters)
    with right:
        with st.container(border=True):
            render_create_roster_table()
            a, b = st.columns(2)
            if a.button("Очистить список", use_container_width=True):
                st.session_state.create_combatants = []
                st.rerun()
            if b.button("Начать бой", use_container_width=True, type="primary"):
                if not st.session_state.create_combatants:
                    st.error("Сначала добавь участников")
                else:
                    temp_encounter = build_encounter_payload(
                        encounter_name.strip() or "Несохранённое столкновение",
                        st.session_state.create_combatants,
                    )
                    st.session_state.battle_state = build_battle_state(temp_encounter)
                    st.session_state.screen = "battle"
                    st.rerun()

    c1, c2 = st.columns([1.05, 1.15])
    with c1:
        with st.container(border=True):
            render_presets_block()
    with c2:
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
    left, mid, right = st.columns([1.1, 1.1, 1.2])
    left.metric("Раунд", battle_state["round"])
    mid.metric("Ход", battle_state["turn_index"] + 1 if battle_state["combatants"] else 0)
    right.metric("Активный участник", active["name"] if active else "—")

    a, b = st.columns([1.3, 1.0])
    if a.button("Следующий ход", type="primary", use_container_width=True):
        next_turn()
        st.rerun()
    if b.button("Завершить бой", use_container_width=True):
        st.session_state.battle_state = None
        st.session_state.selected_monster_sidebar = None
        st.session_state.screen = "create"
        st.rerun()



def render_battle_table(monsters: List[Dict[str, Any]]) -> None:
    battle_state = st.session_state.battle_state
    if not battle_state or not battle_state["combatants"]:
        st.info("Нет участников в текущем бою")
        return

    st.markdown("### Бой")
    render_status_help()

    combatants = battle_state["combatants"]
    active_id = get_active_combatant(battle_state)["id"] if get_active_combatant(battle_state) else None

    header_cols = st.columns([0.45, 2.0, 0.9, 0.8, 1.0, 1.55, 0.95, 1.3, 0.55, 0.55])
    headers = ["#", "Имя", "Тип", "AC", "HP", "Статусы", "Инициатива", "HP-изменение", "↑", "↓"]
    for col, title in zip(header_cols, headers):
        col.markdown(f"**{title}**")

    for idx, combatant in enumerate(combatants):
        normalize_combatant_hp_and_statuses(combatant)
        is_active = combatant["id"] == active_id
        bg = COMBATANT_TYPE_COLORS.get(combatant["type"], "rgba(255,255,255,0.04)")
        outline = ACTIVE_ROW_OUTLINE if is_active else "1px solid rgba(255,255,255,0.08)"

        st.markdown(
            f"<div class='combat-row' style='background:{bg}; border:{outline};'>",
            unsafe_allow_html=True,
        )

        cols = st.columns([0.45, 2.0, 0.9, 0.8, 1.0, 1.55, 0.95, 1.3, 0.55, 0.55])
        cols[0].markdown(f"**{idx + 1}**")

        with cols[1]:
            if combatant["type"] == "monster":
                with st.container(key=f"name_wrap_{combatant['id']}"):
                    st.markdown("<div class='combat-name-button'>", unsafe_allow_html=True)
                    if st.button(combatant["name"], key=f"monster_open_{combatant['id']}", use_container_width=True):
                        st.session_state.selected_monster_sidebar = combatant.get("monster_ref") or combatant["name"]
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                cols[1].markdown(f"**{combatant['name']}**")

        cols[2].markdown(combatant_type_badge(combatant["type"]))
        cols[3].markdown(str(combatant["armor_class"]))
        cols[4].markdown(f"**{combatant['current_hp']} / {combatant['max_hp']}**")

        current_statuses = cols[5].multiselect(
            "Статусы",
            options=list(STATUS_LIBRARY.keys()),
            default=combatant.get("statuses", []),
            label_visibility="collapsed",
            help="; ".join([f"{k}: {v}" for k, v in STATUS_LIBRARY.items()]),
            key=f"statuses_{combatant['id']}",
        )
        if sorted(current_statuses) != sorted(combatant.get("statuses", [])):
            update_combatant_statuses(combatant["id"], current_statuses)
            st.rerun()

        initiative_value = cols[6].number_input(
            "Инициатива",
            value=int(combatant["initiative"]),
            step=1,
            label_visibility="collapsed",
            key=f"init_{combatant['id']}",
        )
        if int(initiative_value) != int(combatant["initiative"]):
            update_combatant_initiative(combatant["id"], int(initiative_value))
            st.rerun()

        with cols[7]:
            hp_delta = st.number_input(
                "HP delta",
                value=0,
                step=1,
                label_visibility="collapsed",
                key=f"hp_delta_{combatant['id']}",
            )
            d1, d2 = st.columns(2)
            if d1.button("Урон", key=f"damage_{combatant['id']}", use_container_width=True):
                apply_hp_delta(combatant["id"], -abs(int(hp_delta)))
                st.rerun()
            if d2.button("Леч.", key=f"heal_{combatant['id']}", use_container_width=True):
                apply_hp_delta(combatant["id"], abs(int(hp_delta)))
                st.rerun()

        if cols[8].button("↑", key=f"up_{combatant['id']}", use_container_width=True):
            move_combatant(combatant["id"], "up")
            st.rerun()

        if cols[9].button("↓", key=f"down_{combatant['id']}", use_container_width=True):
            move_combatant(combatant["id"], "down")
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)



def render_battle_screen(monsters: List[Dict[str, Any]]) -> None:
    st.subheader("Проведение боя")
    render_battle_header()
    render_battle_table(monsters)


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

    tabs_left, tabs_right = st.columns([1.0, 4.5])
    with tabs_left:
        st.markdown("### Навигация")
        if st.button("Создание боя", use_container_width=True, type="primary" if st.session_state.screen == "create" else "secondary"):
            st.session_state.screen = "create"
            st.rerun()
        if st.button("Бой", use_container_width=True, type="primary" if st.session_state.screen == "battle" else "secondary"):
            st.session_state.screen = "battle"
            st.rerun()

    with tabs_right:
        if st.session_state.screen == "battle" and st.session_state.battle_state:
            render_battle_screen(monsters)
        else:
            render_create_screen(monsters)


if __name__ == "__main__":
    main()
