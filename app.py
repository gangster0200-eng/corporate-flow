import os
import re
import hmac
import json
import uuid
import hashlib
import sqlite3
from datetime import datetime, date
from pathlib import Path

import streamlit as st

APP_NAME = "Corporate Flow"
DB_PATH = Path(os.getenv("CORPORATE_FLOW_DB", "corporate_flow.db"))
UPLOAD_DIR = Path(os.getenv("CORPORATE_FLOW_UPLOAD_DIR", "private_uploads"))
MAX_FILE_MB = int(os.getenv("CORPORATE_FLOW_MAX_FILE_MB", "15"))
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".docx", ".xlsx", ".txt"}
ROLES = [
    "Инициатор", "Руководитель", "Финансы", "Юрист",
    "Бухгалтерия", "Казначейство", "Финансовый директор",
    "Аудитор", "Администратор"
]
STATUSES = [
    "Черновик",
    "На проверке казначейства",
    "На проверке финансов",
    "На согласовании финансового директора",
    "Готов к оплате",
    "Оплачен",
    "Отклонён",
    "На доработке",
]


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def add_contract(user, contract_name, contract_number, counterparty, contract_date):
    with db() as conn:
        conn.execute(
            """
            INSERT INTO contracts (
                created_at, created_by, contract_name,
                contract_number, counterparty, contract_date, status
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
    audit(user["username"], "contract_created")

def approve_contract(user, contract_id):
    if user["role"] != "Финансовый директор":
        raise PermissionError("Согласовывать договоры может только финансовый директор.")

    with db() as conn:
        result = conn.execute(
            """
            UPDATE contracts
            SET status = ?, approved_by = ?, approved_at = ?
            WHERE id = ? AND status = ?
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

    audit(user["username"], "contract_approved")
    return True
def init_db():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # Restrict directory permissions where the OS supports it.
    try:
        os.chmod(UPLOAD_DIR, 0o700)
    except OSError:
        pass
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS requests (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            department TEXT NOT NULL,
            counterparty TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            due_date TEXT NOT NULL,
            expense_type TEXT NOT NULL,
            purpose TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            contract_number TEXT,
            status TEXT NOT NULL,
            assigned_to TEXT,
            payment_date TEXT,
            payment_reference TEXT,
            file_path TEXT,
            file_original_name TEXT,
            comments TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TEXT NOT NULL,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            request_id TEXT,
            details TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
        CREATE INDEX IF NOT EXISTS idx_requests_counterparty ON requests(counterparty);
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            contract_name TEXT NOT NULL,
            contract_number TEXT,
            counterparty TEXT NOT NULL,
            contract_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Согласование фин отделом',
            approved_by TEXT,
            approved_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
        """)


def audit(actor, action, request_id=None, details=""):
    with db() as conn:
        conn.execute(
            "INSERT INTO audit_log (occurred_at, actor, action, request_id, details) VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), actor, action, request_id, details[:2000])
        )


def configured_users():
    # Configure users in .streamlit/secrets.toml. Store SHA-256 hashes, never plaintext passwords.
    try:
        users = st.secrets["users"]
        return {name: dict(data) for name, data in users.items()}
    except Exception:
        return {}


def password_hash(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def login():
    users = configured_users()
    st.title("📑 Corporate Flow")
    st.caption("Внутренний сервис согласования договоров и платежей")
    if not users:
        st.error("Не настроены пользователи. Создайте .streamlit/secrets.toml по примеру из README.md.")
        st.stop()
    with st.form("login_form"):
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти", use_container_width=True)
    if submitted:
        user = users.get(username)
        if user and hmac.compare_digest(str(user.get("password_sha256", "")), password_hash(password)):
            st.session_state.user = {
                "username": username,
                "role": str(user.get("role", "Инициатор")),
                "department": str(user.get("department", "Общее"))
            }
            audit(username, "login")
            st.rerun()
        st.error("Неверный логин или пароль.")


def can_view_all(user):
    return user["role"] in {
        "Руководитель", "Финансы", "Юрист", "Бухгалтерия",
        "Казначейство", "Финансовый директор", "Аудитор", "Администратор"
    }


def visible_requests(user):
    with db() as conn:
        rows = conn.execute("SELECT * FROM requests ORDER BY created_at DESC").fetchall()
    if can_view_all(user):
        return rows
    return [r for r in rows if r["created_by"] == user["username"]]


def next_status_options(role, current):
    allowed = {
        "Инициатор": {
            "Черновик": ["На согласовании руководителя"],
            "На доработке": ["На согласовании руководителя"],
        },
        "Руководитель": {
            "На согласовании руководителя": [
                "Отклонен",
                "На доработке",
            ],
        },
        "Финансы": {},
        "Финансовый директор": {
            "На согласовании финансового директора": [
                "Готов к оплате",
                "Отклонен",
                "На доработке",
            ],
        },
        "Бухгалтерия": {},
        "Казначейство": {
            "Готов к оплате": ["Оплачен"],
        },
        "Аудитор": {},
        "Администратор": {},
    }

    return allowed.get(role, {}).get(current, [])


def save_upload(uploaded_file):
    if uploaded_file is None:
        return None, None
    original = Path(uploaded_file.name).name
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Недопустимый формат файла.")
    content = uploaded_file.getvalue()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise ValueError(f"Файл превышает лимит {MAX_FILE_MB} МБ.")
    # Never use the client-provided filename as a storage path.
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    target = UPLOAD_DIR / safe_name
    target.write_bytes(content)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return str(target), original


def request_form(user):
    st.subheader("Новая заявка на оплату")
    with st.form("new_request", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            counterparty = st.text_input("Контрагент *")
            amount = st.number_input("Сумма платежа *", min_value=0.01, value=1000.00, step=100.00)
            currency = st.selectbox("Валюта", ["RUB", "EUR", "USD", "CNY", "KZT", "Другая"])
            due_date = st.date_input("Срок оплаты", value=date.today())
            expense_type = st.selectbox("Тип расхода", [
                "Товары", "Услуги", "Аренда", "Заработная плата",
                "Налоги и сборы", "Командировки", "ИТ", "Прочее"
            ])
        with c2:
            department = st.text_input("Подразделение", value=user["department"])
            purpose = st.text_area("Цель расхода *")
            email = st.text_input("E-mail контрагента")
            phone = st.text_input("Контактный телефон")
            contract_number = st.text_input("Номер договора")
        uploaded = st.file_uploader(
            f"Счёт или документ (до {MAX_FILE_MB} МБ)",
            type=[x.lstrip(".") for x in sorted(ALLOWED_EXTENSIONS)]
        )
        comments = st.text_area("Комментарий")
        submitted = st.form_submit_button("Создать заявку", use_container_width=True)
    if submitted:
        if not counterparty.strip() or not purpose.strip():
            st.error("Заполните обязательные поля: контрагент и цель расхода.")
            return
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            st.error("Проверьте формат e-mail.")
            return
        try:
            file_path, original_name = save_upload(uploaded)
        except ValueError as exc:
            st.error(str(exc))
            return
        request_id = uuid.uuid4().hex[:12].upper()
        status = "Черновик"
        with db() as conn:
            conn.execute("""
                INSERT INTO requests (
                    id, created_at, created_by, department, counterparty, amount, currency,
                    due_date, expense_type, purpose, email, phone, contract_number, status,
                    file_path, file_original_name, comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request_id, datetime.now().isoformat(timespec="seconds"), user["username"],
                department.strip(), counterparty.strip(), float(amount), currency,
                due_date.isoformat(), expense_type, purpose.strip(), email.strip(), phone.strip(),
                contract_number.strip(), status, file_path, original_name, comments.strip()
            ))
        audit(user["username"], "create_request", request_id, f"Контрагент: {counterparty}; сумма: {amount} {currency}")
        st.success(f"Заявка {request_id} создана.")
        st.rerun()


def request_details(user, row):
    st.subheader(f"Заявка {row['id']}")
    left, right = st.columns([2, 1])
    with left:
        st.markdown(f"### {row['counterparty']}")
        st.write(f"**Сумма:** {row['amount']:,.2f} {row['currency']}")
        st.write(f"**Срок оплаты:** {row['due_date']}")
        st.write(f"**Тип расхода:** {row['expense_type']}")
        st.write(f"**Цель:** {row['purpose']}")
        st.write(f"**Подразделение:** {row['department']}")
        st.write(f"**Создал:** {row['created_by']} · {row['created_at']}")
        st.write(f"**Договор:** {row['contract_number'] or '—'}")
        st.write(f"**E-mail:** {row['email'] or '—'} · **Телефон:** {row['phone'] or '—'}")
        st.write(f"**Комментарий:** {row['comments'] or '—'}")
        if row["file_path"] and Path(row["file_path"]).exists():
            # Download only after the app has enforced the user's record-level access.
            st.download_button(
                f"Скачать вложение: {row['file_original_name'] or 'документ'}",
                data=Path(row["file_path"]).read_bytes(),
                file_name=row["file_original_name"] or "document",
                key=f"download_{row['id']}"
            )
    with right:
        st.markdown("#### Текущий статус")
        st.info(row["status"])
        options = next_status_options(user["role"], row["status"])
        if options:
            with st.form(f"status_{row['id']}"):
                new_status = st.selectbox("Изменить статус", options)
                note = st.text_area("Комментарий к решению")
                payment_date = None
                payment_reference = None
                if new_status == "Оплачен":
                    payment_date = st.date_input("Дата оплаты", value=date.today())
                    payment_reference = st.text_input("Номер платёжного поручения")
                change = st.form_submit_button("Сохранить изменение")
            if change:
                if new_status == "Оплачен" and not payment_reference.strip():
                    st.error("Укажите номер платёжного поручения.")
                else:
                    with db() as conn:
                        conn.execute(
                            "UPDATE requests SET status=?, payment_date=?, payment_reference=?, comments=? WHERE id=?",
                            (new_status, payment_date.isoformat() if payment_date else row["payment_date"],
                             payment_reference if payment_reference is not None else row["payment_reference"],
                             note.strip() or row["comments"], row["id"])
                        )
                    audit(user["username"], "status_change", row["id"], f"{row['status']} -> {new_status}; {note}")
                    st.success("Статус обновлён.")
                    st.rerun()
        else:
            st.caption("Для вашей роли нет доступных действий по текущему статусу.")


def main_app():
    user = st.session_state.user
    with st.sidebar:
        st.title("📑 Corporate Flow")
        st.caption(f"{user['username']} · {user['role']}")
        st.title("📑 Corporate Flow")
        st.caption(f"{user['username']} · {user['role']}")
        page = st.radio(
    "Раздел",
    [
        "Обзор",
        "Согласование платежей",
        "Заявки",
        "Согласование договоров",
        "Журнал действий",
    ],
)

    if page == "Обзор":
        st.title("Рабочий стол")
        rows = visible_requests(user)
        total = len(rows)
        waiting = sum(1 for r in rows if r["status"] not in {"Оплачен", "Отклонён"})
        paid = sum(1 for r in rows if r["status"] == "Оплачен")
        overdue = sum(1 for r in rows if r["status"] not in {"Оплачен", "Отклонён"} and r["due_date"] < date.today().isoformat())
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Всего заявок", total)
        c2.metric("В работе", waiting)
        c3.metric("Оплачено", paid)
        c4.metric("Просрочено", overdue)
        st.markdown("### Последние заявки")
        if rows:
            st.dataframe([{
                "Номер": r["id"], "Контрагент": r["counterparty"],
                "Сумма": f"{r['amount']:,.2f} {r['currency']}",
                "Срок": r["due_date"], "Статус": r["status"], "Инициатор": r["created_by"]
            } for r in rows[:10]], use_container_width=True, hide_index=True)
        else:
            st.info("Заявок пока нет.")

    elif page == "Согласование платежей":
        st.title("Согласование платежей")
        request_form(user)

    elif page == "Заявки":
        st.title("Реестр заявок")
        rows = visible_requests(user)
        q = st.text_input("Поиск по номеру заявки или контрагенту")
        status_filter = st.multiselect("Статус", STATUSES)
        filtered = [r for r in rows if (not q or q.lower() in r["id"].lower() or q.lower() in r["counterparty"].lower())
                    and (not status_filter or r["status"] in status_filter)]
        if filtered:
            labels = [f"{r['id']} · {r['counterparty']} · {r['amount']:,.2f} {r['currency']} · {r['status']}" for r in filtered]
            chosen = st.selectbox("Открыть заявку", labels)
            row = filtered[labels.index(chosen)]
            request_details(user, row)
        else:
            st.info("По заданным фильтрам заявок не найдено.")
            
    elif page == "Согласование договоров":
    st.title("Согласование договоров")

    st.subheader("Добавить договор")

    with st.form("contract_form", clear_on_submit=True):
        contract_name = st.text_input("Название договора")
        contract_number = st.text_input("Номер договора")
        counterparty = st.text_input("Контрагент")
        contract_date = st.date_input("Дата договора")
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
            st.success("Договор добавлен и отправлен на согласование финансовому отделу.")
            st.rerun()

    with db() as conn:
        contracts = conn.execute(
            "SELECT * FROM contracts ORDER BY id DESC"
        ).fetchall()

    pending = [
        dict(c) for c in contracts
        if c["status"] == "Согласование фин отделом"
    ]
    approved = [
        dict(c) for c in contracts
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
                f'{c["id"]} · {c["contract_name"]} · {c["counterparty"]}': c["id"]
                for c in pending
            }

            chosen_contract = st.selectbox(
                "Выбери договор для согласования",
                list(contract_options.keys()),
            )

            if st.button("Согласовать договор"):
                if approve_contract(user, contract_options[chosen_contract]):
                    st.success("Договор согласован.")
                    st.rerun()
                else:
                    st.warning("Договор уже согласован или не найден.")
        else:
            st.info("Согласовывать договоры может только финансовый директор.")
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


    elif page == "Журнал действий":
        st.title("Журнал действий")
        if user["role"] not in {"Аудитор", "Администратор", "Финансовый директор"}:
            st.warning("Доступ к журналу ограничен.")
            return
        with db() as conn:
            logs = conn.execute("SELECT * FROM audit_log ORDER BY occurred_at DESC LIMIT 500").fetchall()
        st.dataframe([dict(x) for x in logs], use_container_width=True, hide_index=True)


init_db()
if "user" not in st.session_state:
    login()
else:
    main_app()
