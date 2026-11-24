import sqlite3
import os
import psycopg
import streamlit as st
import hashlib
import hmac
import secrets
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from psycopg.rows import dict_row

import streamlit as st
def apply_corporate_style():
    st.markdown("""
    <style>
    /* Основная палитра */
    :root {
    --navy: #414141;
    --burgundy: #963F4B;
    --gold: #C9A7A7;
    --background: #FFFFFF;
    --text: #414141;
    --muted: #777070;
    --border: #E8DFE0;
}

.stApp {
    background: #FFFFFF;
    color: #414141;
}

[data-testid="stSidebar"] {
    background: #F7F4F4;
    border-right: 1px solid #E8DFE0;
}

[data-testid="stSidebar"] * {
    color: #414141;
}

h1, h2, h3 {
    color: #6F2934 !important;
}

.stButton > button,
.stFormSubmitButton > button {
    background: #963F4B;
    color: #FFFFFF;
    border: 1px solid #963F4B;
    border-radius: 8px;
}

.stButton > button:hover,
.stFormSubmitButton > button:hover {
    background: #6F2934;
    border-color: #6F2934;
    color: #FFFFFF;
}

[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E8DFE0;
    border-top: 3px solid #963F4B;
    border-radius: 10px;
    box-shadow: 0 2px 8px rgba(80, 30, 40, 0.04);
        }
}
    </style>
    """, unsafe_allow_html=True)



# =========================================================
# НАСТРОЙКИ
# =========================================================

st.set_page_config(
    page_title="Corporate Flow",
    page_icon="📑",
    layout="wide",
)

DB_PATH = Path(__file__).resolve().parent / "corporate_flow.db"
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 МБ на файл

ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".png", ".jpg", ".jpeg", ".txt", ".csv",
}

ROLES = [
    "Инициатор",
    "Казначейство",
    "Финансовый менеджер (безналичные платежи)",
    "Финансовый менеджер (нал)",
    "Бухгалтерия",
    "Финансовый директор",
    "Администратор",
]

PAYMENT_STATUSES = [
    "На проверке казначейства",
    "На доработке",
    "Отклонён",
    "На согласовании финансового директора",
    "На оплате (безналично)",
    "На выдаче (нал)",
    "Оплачен",
    "Выдано",
]
CITIES = [
    "Санкт-Петербург",
    "Москва",
    "Нижний Новгород",
    "Красноярск",
    "Тюмень",
    "Волгоград",
    "Саратов",
    "Ростов-на-Дону",
    "Казань",
    "Краснодар",
    "Екатеринбург",
    "Пермь",
    "Новосибирск",
    "Уфа",
]

# =========================================================
# БАЗА ДАННЫХ
# =========================================================
@contextmanager
def db():
    database_url = st.secrets["connections"]["postgresql"]["url"]
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        yield conn
# Логины и соответствующие им роли
USER_ROLES = {
    "initiator": "Инициатор",
    "treasury": "Казначейство",
    "cashless_manager": "Финансовый менеджер (безналичные платежи)",
    "cash_manager": "Финансовый менеджер (нал)",
    "accountant": "Бухгалтерия",
    "cfo": "Финансовый директор",
    "admin": "Администратор",
}

def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        300000,
    ).hex()

def user_exists(username):
    with db() as conn:
        row = conn.execute(
            "SELECT username FROM users WHERE username = %s",
            (username,),
        ).fetchone()
    return row is not None

def user_count():
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM users"
        ).fetchone()
        return row["count"]

def create_user(username, password, full_name, role, department="Общее"):
    username = username.strip().lower()
    full_name = full_name.strip()

    if not username or not full_name:
        raise ValueError("Заполни логин и ФИО сотрудника.")

    if len(password) < 10:
        raise ValueError("Пароль должен содержать не менее 10 символов.")

    allowed_roles = {
    "Инициатор",
    "Казначейство",
    "Финансовый директор",
    "Финансовый менеджер (безналичные платежи)",
    "Финансовый менеджер (наличные платежи)",
    "Администратор",
    "initiator",
    "treasury",
    "cfo",
    "admin",
}

    if role not in allowed_roles:
        raise ValueError("Неизвестная роль пользователя.")

    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)

    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM public.users WHERE username = %s",
            (username,),
        ).fetchone()

        if existing:
            raise ValueError("Такой логин уже существует.")

        conn.execute(
            """
            INSERT INTO public.users (
                username,
                password_hash,
                password_salt,
                role,
                department,
                full_name
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                username,
                password_hash,
                salt,
                role,
                department,
                full_name,
            ),
        )


def user_count():
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM users"
        ).fetchone()
        return row["count"]

def create_user(username, password, full_name, role, department="Общее"):
    username = username.strip().lower()
    full_name = full_name.strip()

    if not username:
        raise ValueError("Укажи логин пользователя.")

    if not full_name:
        raise ValueError("Укажи имя и фамилию сотрудника.")

    if len(password) < 10:
        raise ValueError("Пароль должен содержать не менее 10 символов.")

    allowed_roles = {
    "Инициатор",
    "Казначейство",
    "Финансовый директор",
    "Финансовый менеджер (безналичные платежи)",
    "Финансовый менеджер (наличные платежи)",
    "Администратор",
    "initiator",
    "treasury",
    "cfo",
    "admin",
}

    if role not in allowed_roles:
        raise ValueError("Неизвестная роль пользователя.")

    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)

    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = %s",
            (username,),
        ).fetchone()

        if existing:
            raise ValueError("Пользователь с таким логином уже существует.")

        conn.execute(
            """
            INSERT INTO public.users (
                username,
                password_hash,
                password_salt,
                role,
                department,
                full_name
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                username,
                password_hash,
                salt,
                role,
                department,
                full_name,
            ),
        )

def check_password(username, password):
    username = username.strip().lower()

    with db() as conn:
        row = conn.execute(
            """
            SELECT
                username,
                password_hash,
                password_salt,
                role,
                department,
                full_name
            FROM public.users
            WHERE username = %s
            """,
            (username,),
        ).fetchone()

    if row is None:
        return None

    expected_hash = hash_password(password, row["password_salt"])

    if not secrets.compare_digest(
        expected_hash,
        row["password_hash"],
    ):
        return None

    return {
        "username": row["username"],
        "full_name": row["full_name"] or row["username"],
        "role": row["role"],
        "department": row["department"],
    }












    calculated_hash = hash_password(password, row["password_salt"])

    if not hmac.compare_digest(
        calculated_hash,
        row["password_hash"],
    ):
        return None

    return {
        "username": row["username"],
        "role": row["role"],
    }

def change_password(username, old_password, new_password):
    user = check_password(username, old_password)

    if user is None:
        return False, "Старый пароль введён неверно."

    if len(new_password) < 10:
        return False, "Новый пароль должен содержать не менее 10 символов."

    salt = secrets.token_hex(16)
    password_hash = hash_password(new_password, salt)

    with db() as conn:
        conn.execute(
            """
            UPDATE users
            SET password_hash = %s, password_salt = %s
            WHERE username = %s
            """,
            (password_hash, salt, username),
        )

    audit(username, "password_changed", "user", username)
    return True, "Пароль успешно изменён."





def save_attachments(user, object_type, object_id, uploaded_files):
    if not uploaded_files:
        return

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    for uploaded_file in uploaded_files:
        original_name = Path(uploaded_file.name).name
        extension = Path(original_name).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Формат файла {original_name} не поддерживается."
            )

        file_bytes = uploaded_file.getvalue()

        if len(file_bytes) > MAX_FILE_SIZE:
            raise ValueError(
                f"Файл {original_name} превышает размер 10 МБ."
            )

        stored_name = f"{secrets.token_hex(16)}{extension}"
        stored_path = UPLOAD_DIR / stored_name

        stored_path.write_bytes(file_bytes)

        with db() as conn:
            conn.execute(
                """
                INSERT INTO attachments (
                    object_type, object_id, original_name,
                    stored_name, uploaded_by, uploaded_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    object_type,
                    str(object_id),
                    original_name,
                    stored_name,
                    user["username"],
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

        audit(
    user["username"],
    "payment_request_created",
    "payment",
    request_id,
    (
        f"Создана заявка. Контрагент: {counterparty}; "
        f"сумма: {amount} {currency}; "
        f"срок оплаты: {due_date}"
    ),
)

def get_attachments(object_type, object_id):
    with db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM attachments
            WHERE object_type = %s AND object_id = %s
            ORDER BY uploaded_at DESC
            """,
            (object_type, str(object_id)),
        ).fetchall()

    return [dict(row) for row in rows]

def show_attachments(object_type, object_id):
    files = get_attachments(object_type, object_id)

    if not files:
        st.caption("Прикреплённых файлов пока нет.")
        return

    st.write("**Прикреплённые файлы**")

    for file_info in files:
        file_path = UPLOAD_DIR / file_info["stored_name"]

        if file_path.is_file():
            with open(file_path, "rb") as file_handle:
                st.download_button(
                    label=f'Скачать: {file_info["original_name"]}',
                    data=file_handle.read(),
                    file_name=file_info["original_name"],
                    key=f'file_{object_type}_{object_id}_{file_info["id"]}',
                )
        else:
            st.warning(
                f'Файл {file_info["original_name"]} не найден в хранилище.'
            )
def init_db():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        os.chmod(UPLOAD_DIR, 0o700)
    except OSError:
        pass

    with db() as conn:
        conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        password_salt TEXT NOT NULL,
        role TEXT NOT NULL,
        department TEXT NOT NULL DEFAULT 'Общее'
    )
""")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id BIGSERIAL PRIMARY KEY,
                occurred_at TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                request_id TEXT,
                details TEXT
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_status
            ON requests(status)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_counterparty
            ON requests(counterparty)
        """)



        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id BIGSERIAL PRIMARY KEY,
                occurred_at TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                request_id TEXT,
                details TEXT
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_status
            ON requests(status)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_counterparty
            ON requests(counterparty)
        """)

        # Добавляем новые столбцы в существующую базу данных,
        # если их там ещё нет.
        request_columns = {
            row["column_name"]
            for row in conn.execute(
               "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'requests'"
            ).fetchall()
        }

        if "cashless" not in request_columns:
            conn.execute(
                """
                ALTER TABLE requests
                ADD COLUMN cashless INTEGER NOT NULL DEFAULT 1
                """
            )

        if "assigned_to" not in request_columns:
            conn.execute(
                """
                ALTER TABLE requests
                ADD COLUMN assigned_to TEXT
                """
            )







def audit(actor, action, object_type="", object_id="", details=""):
    with db() as conn:
        columns = {
            row["column_name"]
            for row in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'audit_log'
                """
            ).fetchall()
        }

        occurred_at = datetime.now().isoformat(timespec="seconds")

        if "object_type" in columns and "object_id" in columns:
            conn.execute(
                """
                INSERT INTO audit_log (
                    occurred_at, actor, action,
                    object_type, object_id, details
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    occurred_at,
                    actor,
                    action,
                    object_type,
                    str(object_id),
                    details,
                ),
            )
        elif "request_id" in columns:
            conn.execute(
                """
                INSERT INTO audit_log (
                    occurred_at, actor, action,
                    request_id, details
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    occurred_at,
                    actor,
                    action,
                    str(object_id),
                    details or object_type,
                ),
            )
        else:
            raise RuntimeError(
                "Структура таблицы audit_log не соответствует ожидаемой."
            )






# =========================================================
# ПЛАТЕЖИ
# =========================================================

def create_request(
    user,
    counterparty,
    amount,
    currency,
    due_date,
    purpose,
    contract_number,
    cashless=True,
    city="Не указан",
):
    request_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat(timespec="seconds")

    values = {
        "id": request_id,
        "created_at": created_at,
        "created_by": user["username"],
        "counterparty": counterparty,
        "amount": amount,
        "currency": currency,
        "due_date": str(due_date),
        "purpose": purpose,
        "contract_number": contract_number,
        "status": "На проверке казначейства",
        "comments": "",
        "payment_date": None,
        "payment_reference": None,
        "cashless": int(cashless),
        "expense_type": "Не указан",
        "department": user.get("department", "Не указан"),
        "assigned_to": "Казначейство",
        "city": city,
    }

    with db() as conn:
        existing_columns = {
            row["column_name"]
            for row in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'requests'
                """
            ).fetchall()
        }

        available_values = {
            key: value
            for key, value in values.items()
            if key in existing_columns
        }

        columns = ", ".join(available_values.keys())
        placeholders = ", ".join(
            ["%s"] * len(available_values)
        )

        conn.execute(
            f"""
            INSERT INTO requests ({columns})
            VALUES ({placeholders})
            """,
            list(available_values.values()),
        )

    # Запись о создании заявки в журнале действий
    audit(
        user["username"],
        "payment_request_created",
        "payment",
        request_id,
        (
            f"Создана платёжная заявка. "
            f"Автор: {user.get('full_name') or user['username']}; "
            f"Контрагент: {counterparty}; "
            f"Сумма: {amount} {currency}; "
            f"Дата создания: {created_at}"
        ),
    )

    return request_id










def change_payment_status(
    user,
    request_id,
    new_status,
    comment="",
    payment_reference="",
):
    allowed = {
        "Казначейство": {
            "На согласовании финансового директора",
            "На доработке",
            "Отклонён",
            "Оплачен",
        },
        "Финансовый директор": {
            "Готов к оплате",
            "На доработке",
            "Отклонён",
        },
        "Администратор": set(PAYMENT_STATUSES),
    }

    role = user["role"]

    if new_status not in allowed.get(role, set()):
        raise PermissionError(
            "У вашей роли нет прав на это действие."
        )

    with db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM public.requests
            WHERE id = %s
            """,
            (request_id,),
        ).fetchone()

        if row is None:
            return False

        current_status = row["status"]

        valid_transitions = {
            "На проверке казначейства": {
                "На согласовании финансового директора",
                "На доработке",
                "Отклонён",
            },
            "На согласовании финансового директора": {
                "Готов к оплате",
                "На доработке",
                "Отклонён",
            },
            "Готов к оплате": {"Оплачен"},
            "На доработке": set(),
            "Оплачен": set(),
            "Отклонён": set(),
        }

        if new_status not in valid_transitions.get(
            current_status, set()
        ):
            return False

        payment_date = (
            date.today().isoformat()
            if new_status == "Оплачен"
            else row["payment_date"]
        )

        final_reference = (
            payment_reference.strip()
            if payment_reference.strip()
            else row["payment_reference"]
        )

        final_comment = (
            comment.strip()
            if comment.strip()
            else row["comments"]
        )

        conn.execute(
            """
            UPDATE public.requests
            SET
                status = %s,
                payment_date = %s,
                payment_reference = %s,
                comments = %s
            WHERE id = %s
            """,
            (
                new_status,
                payment_date,
                final_reference,
                final_comment,
                request_id,
            ),
        )

    audit(
        user["username"],
        "payment_status_changed",
        "payment",
        request_id,
        (
            f"Статус изменён: {current_status} → {new_status}. "
            f"Комментарий: {comment.strip() or 'Не указан'}"
        ),
    )

    return True




def get_requests(user):
    with db() as conn:

        # Инициатор видит только собственные заявки
        if user.get("role") in ("Инициатор", "initiator"):
            rows = conn.execute(
                """
                SELECT * FROM requests
                WHERE created_by = %s
                ORDER BY created_at DESC
                """,
                (user["username"],),
            ).fetchall()

        # Остальные роли видят все заявки
        else:
            rows = conn.execute(
                """
                SELECT * FROM requests
                ORDER BY created_at DESC
                """
            ).fetchall()

    return [dict(row) for row in rows]
def delete_payment_request(user, request_id):
    # Удалять заявки может только пользователь admin
    if user.get("username") != "admin":
        raise PermissionError("У тебя нет прав на удаление заявок.")

    # Получаем информацию о прикреплённых файлах
    attachments = get_attachments("payment", request_id)

    # Удаляем заявку и записи о её вложениях из базы данных
    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM requests WHERE id = %s",
            (str(request_id),),
        ).fetchone()

        if not existing:
            raise ValueError("Заявка не найдена.")

        conn.execute(
            """
            DELETE FROM attachments
            WHERE object_type = %s AND object_id = %s
            """,
            ("payment", str(request_id)),
        )

        conn.execute(
            "DELETE FROM requests WHERE id = %s",
            (str(request_id),),
        )

    # Удаляем файлы из локального хранилища
    for attachment in attachments:
        file_path = UPLOAD_DIR / attachment["stored_name"]
        try:
            if file_path.is_file():
                file_path.unlink()
        except OSError:
            pass

    # Записываем действие администратора в журнал
    audit(
        user["username"],
        "payment_request_deleted",
        "payment",
        request_id,
        "Платёжная заявка удалена администратором",
    )

# =========================================================
# ДОГОВОРЫ
# =========================================================

def add_contract(user, contract_name, contract_number,
                 counterparty, contract_date):
    with db() as conn:
        conn.execute(
            "INSERT INTO contracts (created_at, created_by, contract_name, contract_number, counterparty, contract_date, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                datetime.now().isoformat(timespec="seconds"),
                user["username"],
                contract_name.strip(),
                contract_number.strip(),
                counterparty.strip(),
                contract_date.isoformat(),
                "Согласование фин отделом",
            ),
        )

        contract_id = conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

    audit(
        user["username"],


"contract_created",
        "contract",
        contract_id,
    )

def approve_contract(user, contract_id):
    if user["role"] != "Финансовый директор":
        raise PermissionError(
            "Согласовывать договоры может только финансовый директор."
        )

    with db() as conn:
        result = conn.execute(
        "UPDATE contracts SET status = %s, approved_by = %s, approved_at = %s WHERE id = %s AND status = %s",
        (
            "Согласован",
            user["username"],
            datetime.now().isoformat(timespec="seconds"),
            contract_id,
            "Согласование фин отделом",
        ),
    )

        if result.rowcount == 0:
            return False

    audit(
        user["username"],
        "contract_approved",
        "contract",
        contract_id,
    )

    return True

def get_contracts():
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM contracts ORDER BY id DESC"
        ).fetchall()

    return [dict(row) for row in rows]

# =========================================================
# ВХОД В ДЕМОНСТРАЦИОННУЮ ВЕРСИЮ
# =========================================================

def login():
    st.title("Corporate Flow")
    st.caption("Финансовая система сети детских театральных студий")
    st.divider()

    # Первоначальная настройка: создаём администратора
    if user_count() == 0:
        st.subheader("Первоначальная настройка")
        st.info(
            "Создай пароль администратора. После этого "
            "администратор сможет настроить остальные учётные записи."
        )

        with st.form("initial_admin_form"):
            password1 = st.text_input(
                "Пароль администратора",
                type="password",
            )
            password2 = st.text_input(
                "Повтори пароль",
                type="password",
            )
            submitted = st.form_submit_button(
                "Создать администратора",
                use_container_width=True,
            )

        if submitted:
            if password1 != password2:
                st.error("Пароли не совпадают.")
            elif len(password1) < 10:
                st.error("Пароль должен содержать не менее 10 символов.")
            else:
                create_user(
    "admin",
    password1,
    "Администратор",
    "Администратор",
    "Общее",
)

        return

    with st.form("login_form"):
        username = st.text_input("Логин").strip().lower()
        password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button(
            "Войти",
            use_container_width=True,
        )

    if submitted:
        user = check_password(username, password)

        if user is None:
            st.error("Неверный логин или пароль.")
        else:
            st.session_state.user = user
            audit(username, "login")
            st.rerun()
def show_password_change(user):
    st.title("Смена пароля")

    with st.form("change_password_form"):
        old_password = st.text_input(
            "Текущий пароль",
            type="password",
        )
        new_password = st.text_input(
            "Новый пароль",
            type="password",
        )
        confirm_password = st.text_input(
            "Повтори новый пароль",
            type="password",
        )
        submitted = st.form_submit_button("Изменить пароль")

    if submitted:
        if new_password != confirm_password:
            st.error("Новые пароли не совпадают.")
        else:
            success, message = change_password(
                user["username"],
                old_password,
                new_password,
            )
            if success:
                st.success(message)
            else:
                st.error(message)

def show_user_management(user):
    st.title("Управление пользователями")

    if user["role"] != "Администратор":
        st.warning("Этот раздел доступен только администратору.")
        return

    st.subheader("Создать учётную запись")

    roles = [
        "Инициатор",
        "Казначейство",
        "Финансовый директор",
        "Финансовый менеджер (безналичные платежи)",
        "Финансовый менеджер (наличные платежи)",
        "Администратор",
    ]

    with st.form("create_user_form"):
        full_name = st.text_input("ФИО сотрудника")
        username = st.text_input("Логин").strip().lower()
        department = st.text_input(
            "Подразделение",
            value="Общее",
        )
        role = st.selectbox("Роль", roles)
        password1 = st.text_input("Пароль", type="password")
        password2 = st.text_input(
            "Повтори пароль",
            type="password",
        )

        submitted = st.form_submit_button("Создать пользователя")

    if submitted:
        if not full_name.strip():
            st.error("Укажи ФИО сотрудника.")
        elif not username:
            st.error("Укажи логин.")
        elif password1 != password2:
            st.error("Пароли не совпадают.")
        elif len(password1) < 10:
            st.error("Пароль должен содержать не менее 10 символов.")
        else:
            try:
                create_user(
                    username,
                    password1,
                    full_name,
                    role,
                    department,
                )

                audit(
                    user["username"],
                    "user_created",
                    "user",
                    username,
                    f"{full_name}, роль: {role}",
                )

                st.success(
                    f"Учётная запись сотрудника {full_name} создана."
                )
                st.rerun()

            except ValueError as error:
                st.error(str(error))

    st.divider()
    st.subheader("Существующие учётные записи")

    with db() as conn:
        rows = conn.execute(
            """
            SELECT
                username,
                full_name,
                role,
                department
            FROM public.users
            ORDER BY full_name, username
            """
        ).fetchall()

    if rows:
        users = [dict(row) for row in rows]

        st.dataframe(
            users,
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.subheader("Удаление учётной записи")

        deletable_users = [
            u for u in users
            if u["username"] != user["username"]
        ]

        if not deletable_users:
            st.info("Нет других пользователей для удаления.")
            return

        selected_user = st.selectbox(
            "Выбери сотрудника",
            deletable_users,
            format_func=lambda u: (
                f'{u["full_name"] or u["username"]} '
                f'({u["username"]}) — {u["role"]}'
            ),
        )

        st.warning(
            "Удаление учётной записи необратимо. "
            "Сначала убедись, что выбран правильный сотрудник."
        )

        target_username = selected_user["username"]
        confirm_key = f"confirm_delete_user_{target_username}"

        if st.button(
            "Удалить пользователя",
            key=f"delete_user_{target_username}",
        ):
            st.session_state[confirm_key] = True

        if st.session_state.get(confirm_key, False):
            st.error(
                f'Подтверди удаление сотрудника '
                f'{selected_user["full_name"] or target_username} '
                f'({target_username}).'
            )

            col_yes, col_no = st.columns(2)

            with col_yes:
                if st.button(
                    "Да, удалить",
                    key=f"confirm_delete_user_yes_{target_username}",
                ):
                    try:
                        with db() as conn:
                            target = conn.execute(
                                """
                                SELECT username, role
                                FROM public.users
                                WHERE username = %s
                                """,
                                (target_username,),
                            ).fetchone()

                            if target is None:
                                raise ValueError(
                                    "Пользователь уже отсутствует в базе."
                                )

                            if target["username"] == user["username"]:
                                raise PermissionError(
                                    "Нельзя удалить собственную учётную запись."
                                )

                            if target["role"] == "Администратор":
                                admin_count = conn.execute(
                                    """
                                    SELECT COUNT(*) AS total
                                    FROM public.users
                                    WHERE role = 'Администратор'
                                    """
                                ).fetchone()["total"]

                                if admin_count <= 1:
                                    raise PermissionError(
                                        "Нельзя удалить последнего администратора."
                                    )

                            conn.execute(
                                """
                                DELETE FROM public.users
                                WHERE username = %s
                                """,
                                (target_username,),
                            )

                        audit(
                            user["username"],
                            "user_deleted",
                            "user",
                            target_username,
                            (
                                f'Удалён пользователь: '
                                f'{selected_user["full_name"]}, '
                                f'роль: {selected_user["role"]}'
                            ),
                        )

                        st.session_state.pop(confirm_key, None)
                        st.success("Учётная запись удалена.")
                        st.rerun()

                    except (ValueError, PermissionError) as error:
                        st.error(str(error))

                    except Exception as error:
                        st.error(
                            "Не удалось удалить пользователя. "
                            "Возможно, с ним связаны записи в базе данных. "
                            f"Подробности: {error}"
                        )







            with col_no:
                if st.button(
                    "Отмена",
                    key=f"confirm_delete_user_no_{target_username}",
                ):
                    st.session_state.pop(confirm_key, None)
                    st.rerun()

    else:
        st.info("Пользователей пока нет.")
















# =========================================================
# РАЗДЕЛ: ОБЗОР
# =========================================================

def show_payment_calendar():
    import calendar
    from datetime import date, datetime
    from decimal import Decimal

    st.subheader("Платёжный календарь")
    st.caption("Плановые платежи по датам")

    # Получаем месяц и год
    today = date.today()

    if "payment_calendar_year" not in st.session_state:
        st.session_state.payment_calendar_year = today.year

    if "payment_calendar_month" not in st.session_state:
        st.session_state.payment_calendar_month = today.month

    year = st.session_state.payment_calendar_year
    month = st.session_state.payment_calendar_month

    # Получаем платежи из базы данных
    try:
        with db() as conn:
            requests = conn.execute(
                """
                SELECT
                    id,
                    counterparty,
                    amount,
                    currency,
                    due_date,
                    cashless,
                    status
                FROM public.requests
                WHERE due_date IS NOT NULL
                ORDER BY due_date
                """
            ).fetchall()

    except Exception as error:
        st.error(f"Не удалось загрузить платежи: {error}")
        return

    # Преобразуем дату из базы в формат date
    def parse_payment_date(value):
        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        if value:
            try:
                return date.fromisoformat(str(value)[:10])
            except (ValueError, TypeError):
                return None

        return None

    # Подготавливаем платежи
    payments = []

    for request in requests:
        payment_date = parse_payment_date(request["due_date"])

        if payment_date is None:
            continue

        payments.append({
            "id": request["id"],
            "counterparty": request["counterparty"] or "Не указан",
            "amount": request["amount"] or 0,
            "currency": request["currency"] or "RUB",
            "date": payment_date,
            "cashless": request["cashless"],
            "status": request["status"] or "Не указан",
        })

    # Навигация по месяцам
    col1, col2, col3 = st.columns([1, 4, 1])

    with col1:
        if st.button("←", key="calendar_prev"):
            if month == 1:
                st.session_state.payment_calendar_month = 12
                st.session_state.payment_calendar_year = year - 1
            else:
                st.session_state.payment_calendar_month = month - 1
            st.rerun()

    with col2:
        month_names = [
            "Январь", "Февраль", "Март", "Апрель",
            "Май", "Июнь", "Июль", "Август",
            "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
        ]

        st.markdown(
            f"<h3 style='text-align:center'>"
            f"{month_names[month - 1]} {year}"
            f"</h3>",
            unsafe_allow_html=True,
        )

    with col3:
        if st.button("→", key="calendar_next"):
            if month == 12:
                st.session_state.payment_calendar_month = 1
                st.session_state.payment_calendar_year = year + 1
            else:
                st.session_state.payment_calendar_month = month + 1
            st.rerun()

    # Выбираем платежи текущего месяца
    month_payments = [
        p for p in payments
        if p["date"].year == year and p["date"].month == month
    ]

    # Количество платежей по дням
    payments_by_day = {}

    for payment in month_payments:
        day = payment["date"].day
        payments_by_day[day] = payments_by_day.get(day, 0) + 1

    # Создаём календарную сетку
    calendar_matrix = calendar.monthcalendar(year, month)

    selected_date = st.session_state.get(
        "payment_calendar_selected_date", today
    )

    if selected_date.year != year or selected_date.month != month:
        selected_date = date(year, month, 1)
        st.session_state.payment_calendar_selected_date = selected_date

    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    header = st.columns(7)

    for col, weekday in zip(header, weekdays):
        col.markdown(
            f"<div style='text-align:center;color:gray'>"
            f"<b>{weekday}</b></div>",
            unsafe_allow_html=True,
        )

    for week_number, week in enumerate(calendar_matrix):
        columns = st.columns(7)

        for weekday_number, day in enumerate(week):
            with columns[weekday_number]:
                if day == 0:
                    st.write(" ")
                    continue

                payment_count = payments_by_day.get(day, 0)

                button_label = str(day)

                if payment_count:
                    button_label += f" · {payment_count}"
                current_date = date(year, month, day)

                if st.button(
                    button_label,
                    key=f"payment_day_{year}_{month}_{day}",
                    use_container_width=True,
                    type=(
                        "primary"
                        if current_date == selected_date
                        else "secondary"
                    ),
                ):
                    st.session_state.payment_calendar_selected_date = (
                        current_date
                    )
                    st.rerun()

    st.divider()

    # Платежи выбранной даты
    selected_payments = [
        p for p in payments
        if p["date"] == selected_date
    ]

    st.markdown(
        f"### Платежи на {selected_date.strftime('%d.%m.%Y')}"
    )

    if not selected_payments:
        st.info("На выбранную дату платежей нет.")

    else:
        total = Decimal("0")

        for payment in selected_payments:
            amount = Decimal(str(payment["amount"]))
            total += amount

            payment_type = (
                "Безналичная оплата"
                if payment["cashless"]
                else "Наличная оплата"
            )

            with st.container(border=True):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.markdown(
                        f"**{payment['counterparty']}**"
                    )
                    st.caption(
                        f"Заявка №{payment['id']} · {payment_type}"
                    )
                    st.caption(
                        f"Статус: {payment['status']}"
                    )

                with col2:
                    st.markdown(
                        f"**{amount:,.2f} "
                        f"{payment['currency']}**"
                    )

        # Итог по выбранной дате
        currencies = {
            p["currency"] for p in selected_payments
        }

        st.divider()

        if len(currencies) == 1:
            currency = next(iter(currencies))

            st.metric(
                "Общая сумма платежей",
                f"{total:,.2f} {currency}",
            )
        else:
            st.markdown("**Итого по валютам:**")

            for currency in sorted(currencies):
                currency_total = sum(
                    (
                        Decimal(str(p["amount"]))
                        for p in selected_payments
                        if p["currency"] == currency
                    ),
                    Decimal("0"),
                )

                st.write(
                    f"{currency}: {currency_total:,.2f}"
                )

    st.caption(
        f"Всего платежей в месяце: {len(month_payments)}"
    )
def show_dashboard(user):
    st.title("Рабочий стол")

    requests = get_requests(user)
    contracts = get_contracts()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Всего платежей", len(requests))
    c2.metric(
        "В работе",
        sum(
            1 for r in requests
            if r["status"] not in {"Оплачен", "Отклонён"}
        ),
    )
    c3.metric(
        "Оплачено",
        sum(1 for r in requests if r["status"] == "Оплачен"),
    )
    c4.metric(
        "Договоры на согласовании",
        sum(
            1 for c in contracts
            if c["status"] == "Согласование фин отделом"
        ),
    )

    st.subheader("Последние платежи")

    if requests:
        st.dataframe(
            [
                {
                    "Номер": r["id"],
                    "Контрагент": r["counterparty"],
                    "Сумма": f'{r["amount"]:,.2f} {r["currency"]}',
                    "Срок": r["due_date"],
                    "Статус": r["status"],
                    "Инициатор": r["created_by"],
                }
                for r in requests[:10]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Платежей пока нет.")
        

# =========================================================
# РАЗДЕЛ: СОЗДАНИЕ ПЛАТЕЖА
# =========================================================

def show_create_payment(user):
    st.title("Согласование платежа")
    st.caption("Создание новой заявки на оплату")

    with st.form("payment_form", clear_on_submit=True):
        counterparty = st.text_input("Контрагент")

        city = st.selectbox(
            "Город размещения заявки",
            CITIES,
            index=None,
            placeholder="Выберите город",
        )

        amount = st.number_input(
            "Сумма",
            min_value=0.01,
            value=1000.0,
            step=100.0,
        )

        currency = st.selectbox(
            "Валюта",
            ["RUB", "USD", "EUR", "CNY"],
        )

        cashless_label = st.radio(
            "Безналичная оплата",
            ["Да", "Нет"],
            horizontal=True,
            help="Выберите «Да» для безналичного платежа, «Нет» — для выдачи наличных.",
        )

        due_date = st.date_input(
            "Срок оплаты",
            value=date.today(),
        )

        purpose = st.text_area("Назначение платежа")
        contract_number = st.text_input("Номер договора")

        uploaded_files = st.file_uploader(
            "Прикрепить документы к платежу",
            type=[
                "pdf", "doc", "docx", "xls", "xlsx",
                "png", "jpg", "jpeg", "txt", "csv",
            ],
            accept_multiple_files=True,
            help="До 10 МБ на каждый файл.",
        )

        submitted = st.form_submit_button("Создать заявку")

    if submitted:
        if not counterparty.strip() or not purpose.strip():
            st.error("Заполни контрагента и назначение платежа.")

        elif not city:
            st.error("Выбери город размещения заявки.")

        else:
            try:
                request_id = create_request(
                    user=user,
                    counterparty=counterparty,
                    amount=amount,
                    currency=currency,
                    due_date=due_date,
                    purpose=purpose,
                    contract_number=contract_number,
                    cashless=(cashless_label == "Да"),
                    city=city,
                )

                save_attachments(
                    user,
                    "payment",
                    request_id,
                    uploaded_files,
                )

                st.success(
                    f"Заявка {request_id} создана и отправлена в казначейство."
                )
                st.rerun()

            except (ValueError, OSError) as error:
                st.error(str(error))

            except Exception as error:
                st.error(f"Не удалось создать заявку: {error}")










# =========================================================
# РАЗДЕЛ: РЕЕСТР ПЛАТЕЖЕЙ
# =========================================================

def show_payments(user):
    st.title("Реестр заявок")

    requests = get_requests(user)

    search = st.text_input("Поиск по номеру или контрагенту")

    col1, col2 = st.columns(2)

    with col1:
        status_filter = st.multiselect(
            "Фильтр по статусу",
            PAYMENT_STATUSES,
        )

    with col2:
        city_filter = st.selectbox(
            "Фильтр по городу",
            ["Все города"] + CITIES,
        )

    filtered = [
        r for r in requests
        if (
            not search
            or search.lower() in str(r.get("id", "")).lower()
            or search.lower() in str(r.get("counterparty", "")).lower()
        )
        and (
            not status_filter
            or r.get("status") in status_filter
        )
        and (
            city_filter == "Все города"
            or (r.get("city") or "Не указан") == city_filter
        )
    ]

    if not filtered:
        st.info("Заявок по заданным условиям не найдено.")
        return

    st.dataframe(
        [
            {
                "Номер": r["id"],
                "Дата создания": str(r["created_at"])[:10],
                "Инициатор": r["created_by"],
                "Контрагент": r["counterparty"],
                "Город": r.get("city") or "Не указан",
                "Сумма": f'{r["amount"]:,.2f} {r["currency"]}',
                "Срок оплаты": r["due_date"],
                "Статус": r["status"],
            }
            for r in filtered
        ],
        use_container_width=True,
        hide_index=True,
    )

    labels = {
        f'{r["id"]} · {r["counterparty"]} · '
        f'{r["amount"]:,.2f} {r["currency"]} · {r["status"]}': r
        for r in filtered
    }

    chosen_label = st.selectbox(
        "Открыть заявку",
        list(labels.keys()),
    )
    request = labels[chosen_label]

    st.divider()
    st.subheader(f'Заявка {request["id"]}')

    c1, c2 = st.columns(2)

    with c1:
        st.write("**Контрагент:**", request["counterparty"])
        st.write(
            "**Сумма:**",
            f'{request["amount"]:,.2f} {request["currency"]}',
        )
        cashless_value = request.get("cashless")
        payment_type = (
            "Безналичная оплата"
            if cashless_value in (1, "1", True)
            else "Наличная оплата"
        )

        st.write("**Форма оплаты:**", payment_type)
        st.write("**Город:**", request.get("city") or "Не указан")
        st.write("**Срок оплаты:**", request["due_date"])
        st.write("**Договор:**", request["contract_number"] or "—")

    with c2:
        st.write("**Инициатор:**", request["created_by"])
        st.write("**Статус:**", request["status"])
        st.write("**Назначение:**", request["purpose"])
        st.write("**Комментарий:**", request["comments"] or "—")

    show_attachments("payment", request["id"])
    # Повторная отправка заявки инициатором
    if (
        user.get("role") == "Инициатор"
        and request["created_by"] == user["username"]
        and request["status"] in ("На доработке", "Отклонён")
    ):
        st.divider()
        st.subheader("Повторная отправка заявки")

        st.info(
            "Заявка возвращена. Проверь данные, внеси необходимые "
            "изменения и отправь её повторно в казначейство."
        )

        request_id = request["id"]

        due_date_value = request["due_date"]
        if isinstance(due_date_value, str):
            due_date_value = date.fromisoformat(due_date_value)

        with st.form(
            f"resubmit_payment_form_{request_id}"
        ):
            new_counterparty = st.text_input(
                "Контрагент",
                value=request["counterparty"] or "",
            )

            current_city = request.get("city")
            city_index = (
                CITIES.index(current_city)
                if current_city in CITIES
                else None
            )

            new_city = st.selectbox(
                "Город размещения заявки",
                CITIES,
                index=city_index,
                placeholder="Выберите город",
            )

            new_amount = st.number_input(
                "Сумма",
                min_value=0.01,
                value=float(request["amount"]),
                step=100.0,
            )

            new_currency = st.selectbox(
                "Валюта",
                ["RUB", "USD", "EUR", "CNY"],
                index=(
                    ["RUB", "USD", "EUR", "CNY"].index(
                        request["currency"]
                    )
                    if request["currency"] in ["RUB", "USD", "EUR", "CNY"]
                    else 0
                ),
            )

            new_cashless = st.radio(
                "Безналичная оплата",
                ["Да", "Нет"],
                index=(
                    0 if request.get("cashless") else 1
                ),
                horizontal=True,
            )

            new_due_date = st.date_input(
                "Срок оплаты",
                value=due_date_value,
            )

            new_purpose = st.text_area(
                "Назначение платежа",
                value=request["purpose"] or "",
            )

            new_contract_number = st.text_input(
                "Номер договора",
                value=request.get("contract_number") or "",
            )

            resubmit_comment = st.text_area(
                "Комментарий к повторной отправке",
                placeholder="Укажи, какие исправления были внесены...",
            )

            new_files = st.file_uploader(
                "Добавить исправленные документы",
                type=[
                    "pdf", "doc", "docx", "xls", "xlsx",
                    "png", "jpg", "jpeg", "txt", "csv",
                ],
                accept_multiple_files=True,
                key=f"resubmit_files_{request_id}_{user['username']}",
            )

            resubmit = st.form_submit_button(
                "Отправить на повторное согласование"
            )

        if resubmit:
            if not new_counterparty.strip():
                st.error("Заполни контрагента.")

            elif not new_city:
                st.error("Выбери город.")

            elif not new_purpose.strip():
                st.error("Заполни назначение платежа.")

            else:
                try:
                    with db() as conn:
                        current_request = conn.execute(
                            """
                            SELECT *
                            FROM public.requests
                            WHERE id = %s
                            """,
                            (request_id,),
                        ).fetchone()

                        if current_request is None:
                            raise ValueError(
                                "Заявка не найдена."
                            )

                        if current_request["created_by"] != user["username"]:
                            raise PermissionError(
                                "Можно редактировать только собственные заявки."
                            )
                        if current_request["status"] not in (
                            "На доработке",
                            "Отклонён",
                        ):
                            raise ValueError(
                                "Эта заявка больше не доступна для повторной отправки."
                            )

                        old_comments = (
                            current_request["comments"] or ""
                        )

                        if resubmit_comment.strip():
                            updated_comments = (
                                old_comments
                                + "\n\nПовторная отправка: "
                                + resubmit_comment.strip()
                            )
                        else:
                            updated_comments = (
                                old_comments
                                + "\n\nЗаявка отправлена повторно."
                            )

                        conn.execute(
                            """
                            UPDATE public.requests
                            SET
                                counterparty = %s,
                                city = %s,
                                amount = %s,
                                currency = %s,
                                due_date = %s,
                                purpose = %s,
                                contract_number = %s,
                                cashless = %s,
                                status = %s,
                                comments = %s
                            WHERE id = %s
                            """,
                            (
    new_counterparty.strip(),
    new_city,
    new_amount,
    new_currency,
    new_due_date.isoformat(),
    new_purpose.strip(),
    new_contract_number.strip(),
    1 if new_cashless == "Да" else 0,
    "На проверке казначейства",
    updated_comments,
    request_id,
),
                        )

                    if new_files:
                        save_attachments(
                            user,
                            "payment",
                            request_id,
                            new_files,
                        )

                    audit(
                        user["username"],
                        "payment_request_resubmitted",
                        "payment",
                        request_id,
                        (
                            "Заявка повторно отправлена в казначейство. "
                            f"Контрагент: {new_counterparty.strip()}; "
                            f"сумма: {new_amount} {new_currency}"
                        ),
                    )

                    st.success(
                        "Заявка успешно отправлена на повторное согласование!"
                    )
                    st.rerun()

                except (ValueError, PermissionError, OSError) as error:
                    st.error(str(error))

                except Exception as error:
                    st.error(
                        f"Не удалось повторно отправить заявку: {error}"
                    )

    if user.get("username") == "admin":
        request_id = request["id"]
        confirm_key = f"confirm_delete_payment_{request_id}"

        if st.button(
            "🗑️ Удалить заявку",
            key=f"delete_payment_{request_id}",
        ):
            st.session_state[confirm_key] = True

        if st.session_state.get(confirm_key, False):
            st.warning(
                f"Ты действительно хочешь удалить заявку №{request_id}? "
                "Восстановить её через приложение будет нельзя."
            )

            col_confirm, col_cancel = st.columns(2)

            with col_confirm:
                if st.button(
                    "Да, удалить",
                    key=f"confirm_yes_{request_id}",
                ):
                    try:
                        delete_payment_request(user, request_id)

                        st.session_state.pop(confirm_key, None)

                        st.success("Заявка удалена.")
                        st.rerun()

                    except (ValueError, PermissionError) as error:
                        st.error(str(error))

            with col_cancel:
                if st.button(
                    "Отмена",
                    key=f"confirm_no_{request_id}",
                ):
                    st.session_state.pop(confirm_key, None)
                    st.rerun()

















    role = user["role"]
    status = request["status"]

    st.subheader("Действия")

    if (
        role == "Казначейство"
        and status == "На проверке казначейства"
    ):
        comment = st.text_input("Комментарий казначейства")

        c1, c2, c3 = st.columns(3)

        if c1.button("Передать директору", use_container_width=True):
            if change_payment_status(
                user, request["id"],
                "На согласовании финансового директора",
                comment,
            ):
                st.success("Заявка передана финансовому директору.")
                st.rerun()
            else:
                st.error("Не удалось изменить статус.")

        if c2.button("Вернуть на доработку", use_container_width=True):
            if change_payment_status(
                user, request["id"], "На доработке", comment
            ):
                st.rerun()

        if c3.button("Отклонить", use_container_width=True):
            if change_payment_status(
                user, request["id"], "Отклонён", comment
            ):
                st.rerun()

    elif (
        role == "Финансовый директор"
        and status == "На согласовании финансового директора"
    ):
        comment = st.text_input("Комментарий финансового директора")

        c1, c2, c3 = st.columns(3)

        if c1.button("Согласовать", use_container_width=True):
            if change_payment_status(
                user, request["id"], "Готов к оплате", comment
            ):
                st.success("Заявка согласована.")
                st.rerun()

        if c2.button("Вернуть на доработку", use_container_width=True):
            if change_payment_status(
                user, request["id"], "На доработке", comment
            ):
                st.rerun()

        if c3.button("Отклонить", use_container_width=True):
            if change_payment_status(
                user, request["id"], "Отклонён", comment
            ):
                st.rerun()

    elif role == "Казначейство" and status == "Готов к оплате":
        payment_reference = st.text_input(
            "Номер платёжного поручения или подтверждение оплаты"
        )

        if st.button("Отметить как оплаченную", use_container_width=True):
            if not payment_reference.strip():
                st.error("Укажи реквизиты подтверждения оплаты.")
            elif change_payment_status(
                user,
                request["id"],
                "Оплачен",
                payment_reference=payment_reference,
            ):
                st.success("Платёж отмечен как оплаченный.")
                st.rerun()

    elif (
    request["created_by"] == user["username"]
    and status in ("На доработке", "Отклонён")
):
        st.warning(
            "Заявка возвращена. Исправь необходимые данные "
            "и отправь её повторно на согласование."
        )

        request_id = request["id"]

        due_date_value = request["due_date"]
        if isinstance(due_date_value, str):
            due_date_value = date.fromisoformat(due_date_value)

        with st.form(
    f"resubmit_payment_form_{request_id}_{user['username']}"
):

            new_counterparty = st.text_input(
                "Контрагент",
                value=request["counterparty"] or "",
            )

            current_city = request.get("city")
            city_index = (
                CITIES.index(current_city)
                if current_city in CITIES
                else None
            )

            new_city = st.selectbox(
                "Город размещения заявки",
                CITIES,
                index=city_index,
                placeholder="Выберите город",
            )

            new_amount = st.number_input(
                "Сумма",
                min_value=0.01,
                value=float(request["amount"]),
                step=100.0,
            )

            currencies = ["RUB", "USD", "EUR", "CNY"]
            current_currency = request.get("currency")

            new_currency = st.selectbox(
                "Валюта",
                currencies,
                index=(
                    currencies.index(current_currency)
                    if current_currency in currencies
                    else 0
                ),
            )

            new_cashless = st.radio(
                "Безналичная оплата",
                ["Да", "Нет"],
                index=0 if request.get("cashless") else 1,
                horizontal=True,
            )

            new_due_date = st.date_input(
                "Срок оплаты",
                value=due_date_value,
            )

            new_purpose = st.text_area(
                "Назначение платежа",
                value=request["purpose"] or "",
            )

            new_contract_number = st.text_input(
                "Номер договора",
                value=request.get("contract_number") or "",
            )

            resubmit_comment = st.text_area(
                "Комментарий к повторной отправке",
                placeholder="Какие исправления были внесены?",
            )

            new_files = st.file_uploader(
                "Добавить исправленные документы",
                type=[
                    "pdf", "doc", "docx", "xls", "xlsx",
                    "png", "jpg", "jpeg", "txt", "csv",
                ],
                accept_multiple_files=True,
                key=f"resubmit_files_{request_id}",
            )

            resubmit = st.form_submit_button(
                "Отправить на повторное согласование",
                use_container_width=True,
            )

        if resubmit:
            if not new_counterparty.strip():
                st.error("Заполни контрагента.")

            elif not new_city:
                st.error("Выбери город.")

            elif not new_purpose.strip():
                st.error("Заполни назначение платежа.")

            else:
                try:
                    with db() as conn:
                        current_request = conn.execute(
                            """
                            SELECT *
                            FROM public.requests
                            WHERE id = %s
                            """,
                            (request_id,),
                        ).fetchone()

                        if current_request is None:
                            raise ValueError(
                                "Заявка не найдена."
                            )

                        if current_request["created_by"] != user["username"]:
                            raise PermissionError(
                                "Можно редактировать только собственные заявки."


)

                        if current_request["status"] not in (
                            "На доработке",
                            "Отклонён",
                        ):
                            raise ValueError(
                                "Заявка больше не доступна для повторной отправки."
                            )

                        old_comments = (
                            current_request["comments"] or ""
                        )

                        updated_comments = old_comments

                        if resubmit_comment.strip():
                            updated_comments += (
                                "\n\nПовторная отправка: "
                                + resubmit_comment.strip()
                            )
                        else:
                            updated_comments += (
                                "\n\nЗаявка отправлена повторно."
                            )

                        conn.execute(
                            """
                            UPDATE public.requests
                            SET
                                counterparty = %s,
                                city = %s,
                                amount = %s,
                                currency = %s,
                                due_date = %s,
                                purpose = %s,
                                contract_number = %s,
                                cashless = %s,
                                status = %s,
                                comments = %s
                            WHERE id = %s
                            """,
                            (
                                new_counterparty.strip(),
                                new_city,
                                new_amount,
                                new_currency,
                                new_due_date.isoformat(),
                                new_purpose.strip(),
                                new_contract_number.strip(),
                                1 if new_cashless == "Да" else 0,
                                "На проверке казначейства",
                                updated_comments,
                                request_id,
                            ),
                        )

                    if new_files:
                        save_attachments(
                            user,
                            "payment",
                            request_id,
                            new_files,
                        )

                    audit(
                        user["username"],
                        "payment_request_resubmitted",
                        "payment",
                        request_id,
                        (
                            "Заявка повторно отправлена в казначейство. "
                            f"Контрагент: {new_counterparty.strip()}; "
                            f"сумма: {new_amount} {new_currency}"
                        ),
                    )

                    st.success(
                        "Заявка повторно отправлена в казначейство!"
                    )
                    st.rerun()

                except (ValueError, PermissionError, OSError) as error:
                    st.error(str(error))

                except Exception as error:
                    st.error(
                        f"Не удалось повторно отправить заявку: {error}"
                    )

    elif (
        request["created_by"] == user["username"]
        and status in ("На доработке", "Отклонён")
    ):
        # Здесь должен находиться код редактирования заявки
        st.info("Заявка требует доработки или была отклонена.")

    elif status == "Оплачен":
        st.success(
            f'Оплачено: {request["payment_date"] or "дата не указана"}'
        )

    else:
        st.info("Для вашей роли сейчас нет доступных действий с заявкой.")





# =========================================================
# РАЗДЕЛ: СОГЛАСОВАНИЕ ДОГОВОРОВ
# =========================================================

def show_contracts(user):
    st.title("Согласование договоров")

    st.subheader("Добавить договор")

    with st.form("contract_form", clear_on_submit=True):
        contract_name = st.text_input("Название договора")
        contract_number = st.text_input("Номер договора")
        counterparty = st.text_input("Контрагент")
        contract_date = st.date_input(
            "Дата договора",
            value=date.today(),
        )
        uploaded_files = st.file_uploader(
            "Прикрепить договор и приложения",
            type=[
                "pdf", "doc", "docx", "xls", "xlsx",
                "png", "jpg", "jpeg", "txt", "csv",
            ],
            accept_multiple_files=True,
            help="До 10 МБ на каждый файл.",
        )
        submitted = st.form_submit_button("Добавить договор")

    if submitted:
        if not contract_name.strip() or not counterparty.strip():
            st.error("Укажи название договора и контрагента.")
        else:
            try:
                add_contract(
                    user,
                    contract_name,
                    contract_number,
                    counterparty,
                    contract_date,
                )

                contracts = get_contracts()
                contract_id = contracts[0]["id"]

                save_attachments(
                    user,
                    "contract",
                    contract_id,
                    uploaded_files,
                )

                st.success(
                    f"Договор №{contract_id} добавлен и отправлен на согласование."
                )
                st.rerun()

            except (ValueError, OSError) as error:
                st.error(str(error))







    contracts = get_contracts()

    pending = [
        c for c in contracts
        if c["status"] == "Согласование фин отделом"
    ]

    approved = [
        c for c in contracts
        if c["status"] == "Согласован"
    ]

    st.divider()
    st.subheader("Согласование фин отделом")

    if pending:
        st.dataframe(
            [
                {
                    "№": c["id"],
                    "Название": c["contract_name"],
                    "Номер договора": c["contract_number"] or "—",
                    "Контрагент": c["counterparty"],
                    "Дата": c["contract_date"],
                    "Добавил": c["created_by"],
                    "Статус": c["status"],
                }
                for c in pending
            ],
            use_container_width=True,
            hide_index=True,
        )

        if user["role"] == "Финансовый директор":
            contract_options = {
                f'{c["id"]} · {c["contract_name"]} · '
                f'{c["counterparty"]}': c["id"]
                for c in pending


}

            selected = st.selectbox(
                "Выбери договор для согласования",
                list(contract_options.keys()),
            )

            if st.button("Согласовать договор", use_container_width=True):
                if approve_contract(
                    user,
                    contract_options[selected],
                ):
                    st.success("Договор согласован.")
                    st.rerun()
                else:
                    st.warning(
                        "Договор уже согласован или не найден."
                    )
        else:
            st.info(
                "Согласовывать договоры может только "
                "финансовый директор."
            )
    else:
        st.info("Договоров, ожидающих согласования, пока нет.")

    st.divider()
    st.subheader("Согласованные договоры")

    if approved:
        st.dataframe(
            [
                {
                    "№": c["id"],
                    "Название": c["contract_name"],
                    "Номер договора": c["contract_number"] or "—",
                    "Контрагент": c["counterparty"],
                    "Дата": c["contract_date"],
                    "Согласовал": c["approved_by"] or "—",
                    "Дата согласования": c["approved_at"] or "—",
                    "Статус": c["status"],
                }
                for c in approved
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Согласованных договоров пока нет.")
        st.divider()
        st.subheader("Прикреплённые документы договоров")

    if contracts:
        contract_options = {
            f'{c["id"]} · {c["contract_name"]} · {c["counterparty"]}': c["id"]
            for c in contracts
        }

        selected_contract = st.selectbox(
            "Выбери договор для просмотра файлов",
            list(contract_options.keys()),
            key="contract_files_select",
        )

        selected_contract_id = contract_options[selected_contract]

        show_attachments("contract", selected_contract_id)
    else:
        st.info("Сначала добавь договор.")

# =========================================================
# РАЗДЕЛ: ЖУРНАЛ ДЕЙСТВИЙ
# =========================================================

def show_audit_log(user):
    st.title("Журнал действий")

    if user["role"] not in {
        "Администратор",
        "Финансовый директор",
    }:
        st.warning("Доступ к журналу ограничен.")
        return

    with db() as conn:
        rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY occurred_at DESC LIMIT 500"
    ).fetchall()

    if rows:
        st.dataframe(
            [dict(row) for row in rows],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Записей в журнале пока нет.")

# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

def main_app():
    user = st.session_state.user

    st.title("📑 Corporate Flow")
    st.caption(f'{user["username"]} · {user["role"]}')

    menu_options = [
        "Обзор",
        "Согласование платежа",
        "Заявки",
        "Платёжный календарь",
        "Согласование договоров",
        "Журнал действий",
    ]

    # Навигация
    page = st.sidebar.radio(
        "Навигация",
        menu_options,
        key="main_navigation",
    )

    # Выход в боковом меню
    with st.sidebar:
        st.divider()

        st.markdown(f"**Пользователь:** {user['Username']}")
        st.markdown(f"**Роль:** {user['role']}")

        st.markdown(
            """
            <style>
            div.stButton > button[kind="secondary"] {
                background-color: #FFFFFF;
                color: #963F4B;
                border: 1px solid #963F4B;
                font-weight: 600;
            }

            div.stButton > button[kind="secondary"]:hover {
                background-color: #F7F4F4;
                color: #762D38;
                border-color: #762D38;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "Выйти",
            key="logout_button",
            use_container_width=True,
            type="secondary",
        ):
            audit(user["username"], "logout")
            del st.session_state.user
            st.rerun()




    # Отображение разделов
    if page == "Обзор":
        show_dashboard(user)

    elif page == "Платёжный календарь":
        show_payment_calendar()

    elif page == "Согласование платежа":
        show_create_payment(user)

    elif page == "Заявки":
        show_payments(user)

    elif page == "Согласование договоров":
        show_contracts(user)

    elif page == "Журнал действий":
        show_audit_log(user)

    elif page == "Смена пароля":
        show_password_change(user)

    elif page == "Управление пользователями":
        show_user_management(user)




# =========================================================
# ЗАПУСК
# =========================================================

init_db()
apply_corporate_style()

if "user" not in st.session_state:
    login()
else:
    main_app()
