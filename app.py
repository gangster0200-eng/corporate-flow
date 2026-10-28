import sqlite3
import hashlib
import hmac
import secrets
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

import streamlit as st

# =========================================================
# НАСТРОЙКИ
# =========================================================

st.set_page_config(
    page_title="Corporate Flow",
    page_icon="📑",
    layout="wide",
)

DB_PATH = Path(__file__).resolve().parent / "corporate_flow.db"

ROLES = [
    "Инициатор",
    "Казначейство",
    "Финансовый директор",
    "Аудитор",
    "Администратор",
]

PAYMENT_STATUSES = [
    "На проверке казначейства",
    "На согласовании финансового директора",
    "Готов к оплате",
    "Оплачен",
    "На доработке",
    "Отклонён",
]

# =========================================================
# БАЗА ДАННЫХ
# =========================================================

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
# Логины и соответствующие им роли
USER_ROLES = {
    "initiator": "Инициатор",
    "treasury": "Казначейство",
    "cfo": "Финансовый директор",
    "auditor": "Аудитор",
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
            "SELECT username FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return row is not None

def user_count():
    with db() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

def create_user(username, password):
    if username not in USER_ROLES:
        raise ValueError("Неизвестный логин.")

    if len(password) < 10:
        raise ValueError("Пароль должен содержать не менее 10 символов.")

    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)

    with db() as conn:
        conn.execute(
            """
            INSERT INTO users (
                username, role, password_hash,
                password_salt, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username,
                USER_ROLES[username],
                password_hash,
                salt,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

def check_password(username, password):
    with db() as conn:
        row = conn.execute(
            """
            SELECT username, role, password_hash, password_salt
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

    if row is None:
        return None

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
            SET password_hash = ?, password_salt = ?
            WHERE username = ?
            """,
            (password_hash, salt, username),
        )

    audit(username, "password_changed", "user", username)
    return True, "Пароль успешно изменён."






def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                counterparty TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                due_date TEXT NOT NULL,
                purpose TEXT NOT NULL,
                contract_number TEXT,
                status TEXT NOT NULL,
                comments TEXT,
                payment_date TEXT,
                payment_reference TEXT
            );

            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                contract_name TEXT NOT NULL,
                contract_number TEXT,
                counterparty TEXT NOT NULL,
                contract_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT
                    'Согласование фин отделом',
                approved_by TEXT,
                approved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                object_type TEXT,
                object_id TEXT,
                details TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_requests_status
                ON requests(status);

            CREATE INDEX IF NOT EXISTS idx_contracts_status
                ON contracts(status);
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

def audit(actor, action, object_type="", object_id="", details=""):
    with db() as conn:
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(audit_log)"
            ).fetchall()
        }

        if "object_type" in columns and "object_id" in columns:
            conn.execute(
                """
                INSERT INTO audit_log (
                    occurred_at, actor, action,
                    object_type, object_id, details
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(timespec="seconds"),
                    actor,
                    action,
                    object_type,
                    str(object_id),
                    details,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO audit_log (
                    occurred_at, actor, action,
                    request_id, details
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(timespec="seconds"),
                    actor,
                    action,
                    str(object_id),
                    details or object_type,
                ),
            )
# =========================================================
# ПЛАТЕЖИ
# =========================================================

def create_request(user, counterparty, amount, currency,
                   due_date, purpose, contract_number):
    request_id = str(uuid.uuid4())[:8].upper()

    with db() as conn:
        conn.execute(
            """
            INSERT INTO requests (
                id, created_at, created_by, counterparty,
                amount, currency, due_date, purpose,
                contract_number, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id, time.now().isoformat(timespec="seconds"),
                user["username"],
                counterparty.strip(),
                amount,
                currency,
                due_date.isoformat(),
                purpose.strip(),
                contract_number.strip(),
                "На проверке казначейства",
            ),
        )

    audit(
        user["username"],
        "payment_created",
        "payment",
        request_id,
    )

def change_payment_status(user, request_id, new_status,
                          comment="", payment_reference=""):
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
            "SELECT * FROM requests WHERE id = ?",
            (request_id,),
        ).fetchone()

        if row is None:
            return False

        current_status = row["status"]

        # Проверяем последовательность согласования.
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

        conn.execute(
            """
            UPDATE requests
            SET status = ?,
                comments = ?,
                payment_date = ?,
                payment_reference = ?
            WHERE id = ?
            """,
            (
                new_status,
                comment.strip() or row["comments"],
                payment_date,
                payment_reference.strip()
                or row["payment_reference"],
                request_id,
            ),
        )

    audit(
        user["username"],
        "payment_status_changed",
        "payment",
        request_id,
        f"{current_status} -> {new_status}",
    )

    return True

def get_requests():
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM requests ORDER BY created_at DESC"
        ).fetchall()

    return [dict(row) for row in rows]

# =========================================================
# ДОГОВОРЫ
# =========================================================

def add_contract(user, contract_name, contract_number,
                 counterparty, contract_date):
    with db() as conn:
        conn.execute(
            """
            INSERT INTO contracts (
                created_at, created_by, contract_name,
                contract_number, counterparty,
                contract_date, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
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
            """
            UPDATE contracts
            SET status = ?,
                approved_by = ?,
                approved_at = ?
            WHERE id = ?
              AND status = ?
            """,
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
    st.title("📑 Corporate Flow")
    st.caption("Вход в систему")

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
                create_user("admin", password1)
                st.success(
                    "Администратор создан. Теперь войди с логином admin."
                )
                st.rerun()

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

    with st.form("create_user_form"):
        available_users = [
            username
            for username in USER_ROLES
            if not user_exists(username)
        ]

        if not available_users:
            st.info("Все предусмотренные учётные записи уже созданы.")
            return

        username = st.selectbox(
            "Должность / логин",
            available_users,
            format_func=lambda name: (
                f"{USER_ROLES[name]} ({name})"
            ),
        )
        password1 = st.text_input(
            "Пароль",
            type="password",
        )
        password2 = st.text_input(
            "Повтори пароль",
            type="password",
        )
        submitted = st.form_submit_button("Создать пользователя")

    if submitted:
        if password1 != password2:
            st.error("Пароли не совпадают.")
        elif len(password1) < 10:
            st.error("Пароль должен содержать не менее 10 символов.")
        else:
            create_user(username, password1)
            audit(
                user["username"],
                "user_created",
                "user",
                username,
            )
            st.success(
                f"Создан пользователь {username} "
                f"({USER_ROLES[username]})."
            )
            st.rerun()

    st.divider()
    st.subheader("Существующие учётные записи")

    with db() as conn:
        rows = conn.execute(
            """
            SELECT username, role, created_at
            FROM users
            ORDER BY username
            """
        ).fetchall()

    if rows:
        st.dataframe(
            [dict(row) for row in rows],
            use_container_width=True,
            hide_index=True,
        )











# =========================================================
# РАЗДЕЛ: ОБЗОР
# =========================================================

def show_dashboard():
    st.title("Рабочий стол")

    requests = get_requests()
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
        due_date = st.date_input(
            "Срок оплаты",
            value=date.today(),
        )
        purpose = st.text_area("Назначение платежа")
        contract_number = st.text_input("Номер договора")

        submitted = st.form_submit_button("Создать заявку")

    if submitted:
        if not counterparty.strip() or not purpose.strip():
            st.error("Заполни контрагента и назначение платежа.")
        else:
            create_request(
                user,
                counterparty,
                amount,
                currency,
                due_date,
                purpose,
                contract_number,
            )
            st.success("Заявка создана и отправлена в казначейство.")
            st.rerun()

# =========================================================
# РАЗДЕЛ: РЕЕСТР ПЛАТЕЖЕЙ
# =========================================================

def show_payments(user):
    st.title("Реестр заявок")

    requests = get_requests()

    search = st.text_input("Поиск по номеру или контрагенту")
    status_filter = st.multiselect(
        "Фильтр по статусу",
        PAYMENT_STATUSES,
    )

    filtered = [
        r for r in requests
        if (
            not search
            or search.lower() in r["id"].lower()
            or search.lower() in r["counterparty"].lower()
        )
        and (
            not status_filter
            or r["status"] in status_filter
        )
    ]

    if not filtered:
        st.info("Заявок по заданным условиям не найдено.")
        return

    st.dataframe(
        [
            {
                "Номер": r["id"],
                "Дата создания": r["created_at"][:10],
                "Инициатор": r["created_by"],
                "Контрагент": r["counterparty"],
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
        st.write("**Срок оплаты:**", request["due_date"])
        st.write("**Договор:**", request["contract_number"] or "—")

    with c2:
        st.write("**Инициатор:**", request["created_by"])
        st.write("**Статус:**", request["status"])
        st.write("**Назначение:**", request["purpose"])
        st.write("**Комментарий:**", request["comments"] or "—")

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

    elif status == "На доработке":
        st.info(
            "Заявка возвращена на доработку. "
            "В этой демонстрационной версии повторная отправка "
            "на согласование пока не реализована."
        )

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
        submitted = st.form_submit_button("Добавить договор")

    if submitted:
        if not contract_name.strip() or not counterparty.strip():
            st.error("Укажи название договора и контрагента.")
        else:
            add_contract(
                user,
                contract_name,
                contract_number,
                counterparty,
                contract_date,
            )
            st.success(
                "Договор добавлен и отправлен на согласование "
                "финансовому отделу."
            )
            st.rerun()

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

# =========================================================
# РАЗДЕЛ: ЖУРНАЛ ДЕЙСТВИЙ
# =========================================================

def show_audit_log(user):
    st.title("Журнал действий")

    if user["role"] not in {
        "Аудитор",
        "Администратор",
        "Финансовый директор",
    }:
        st.warning("Доступ к журналу ограничен.")
        return

    with db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM audit_log
            ORDER BY occurred_at DESC
            LIMIT 500
            """
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

    page = st.radio(
        "Раздел",
        [
            "Обзор",
            "Согласование платежа",
            "Заявки",
            "Согласование договоров",
            "Смена пароля",
            "Управление пользователями",
            "Журнал действий",
        ],
    )

    if st.button("Выйти"):
        audit(user["username"], "logout")
        del st.session_state.user
        st.rerun()

    st.divider()

    if page == "Обзор":
        show_dashboard()

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

if "user" not in st.session_state:
    login()
else:
    main_app() 
