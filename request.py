import requests
import re
import sys
import xml.etree.ElementTree as ET
import json
from dotenv import load_dotenv
import os
from collections import Counter, defaultdict

# Абсолютные пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = f"{BASE_DIR}/.session_id.txt"
ENV_FILE = f"{BASE_DIR}/.env"

# Загрузка переменных окружения
load_dotenv(dotenv_path=ENV_FILE)
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

AUTH_URL = "https://my.activecloud.com/ru/staffapi/index.php?/Core/Default/Login"
TICKETS_URL = "https://my.activecloud.com/ru/staffapi/index.php?/Tickets/Retrieve"


def save_session_id(session_id: str) -> None:
    """
    Сохраняет session_id в файл.
    """
    with open(SESSION_FILE, "w") as file:
        file.write(session_id)


def load_session_id() -> str:
    """
    Загружает session_id из файла.
    """
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as file:
            return file.read().strip()
    return None


def get_session_id(username: str, password: str) -> str:
    """
    Получение нового session_id для авторизации.
    """
    response = requests.post(
        AUTH_URL,
        data={"username": username, "password": password},
        headers={"Accept-Encoding": "gzip, deflate"}
    )

    if response.ok:
        match = re.search(r'(\w{32})', response.text)
        if match:
            session_id = match.group(1)
            save_session_id(session_id)
            return session_id
        raise ValueError("Session ID не найден в ответе.")
    response.raise_for_status()


def is_session_valid(response: requests.Response) -> bool:
    """
    Проверяет, действительна ли сессия, анализируя XML-ответ.
    """
    try:
        root = ET.fromstring(response.content.decode("utf-8", errors="ignore"))
        status = root.find(".//status")
        if status is not None and status.text == "-2":
            return False
    except ET.ParseError:
        pass
    return True


def get_open_tickets(session_id: str, department_ids: list) -> list:
    """
    Получение открытых заявок для указанных департаментов.
    """
    all_tickets = []
    for department_id in department_ids:
        response = requests.post(
            TICKETS_URL,
            data={"sessionid": session_id, "departmentid": department_id, "statusid": "4"},
            headers={"Accept-Encoding": "gzip, deflate"}
        )

        # Если сессия истекла, возвращаем сигнал для обновления session_id
        if not is_session_valid(response):
            raise ValueError("Сессия истекла, требуется повторная авторизация.")

        if not response.ok:
            response.raise_for_status()

        try:
            root = ET.fromstring(response.content.decode("utf-8", errors="ignore"))
            tickets = [
                {
                    "id": ticket.get("id"),
                    "subject": ticket.find("subject").text if ticket.find("subject") is not None else "Без темы",
                    "departmenttitle": ticket.find("departmenttitle").text if ticket.find("departmenttitle") is not None else "Неизвестный департамент",
                    "userorganization": ticket.find("userorganization").text if ticket.find("userorganization") is not None else "Неизвестная организация"
                }
                for ticket in root.findall(".//ticket")
            ]
            all_tickets.extend(tickets)
        except ET.ParseError as e:
            raise ValueError(f"Ошибка парсинга XML для департамента {department_id}: {e}")
    return all_tickets


def count_department_titles(tickets: list) -> dict:
    """
    Подсчет количества заявок по каждому departmenttitle.
    """
    department_titles = [ticket["departmenttitle"] for ticket in tickets]
    return dict(Counter(department_titles))


def save_to_file(data: list, filename: str) -> None:
    """
    Сохранение данных в JSON файл.
    """
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def group_tickets_by_department(tickets: list) -> dict:
    """
    Группировка заявок по полю departmenttitle.
    """
    grouped_tickets = defaultdict(list)
    for ticket in tickets:
        department = ticket["departmenttitle"]
        grouped_tickets[department].append(ticket)
    return grouped_tickets

def main():
    """
    Основная функция.
    """
    try:
        session_id = load_session_id()
        if not session_id:
            print("Сессия отсутствует, выполняется авторизация...")
            session_id = get_session_id(USERNAME, PASSWORD)

        department_ids = ["6", "11", "70", "71", "100", "108"]
        try:
            tickets = get_open_tickets(session_id, department_ids)
        except ValueError as e:
            if "Сессия истекла" in str(e):
                print("Сессия истекла, выполняется повторная авторизация...")
                session_id = get_session_id(USERNAME, PASSWORD)
                tickets = get_open_tickets(session_id, department_ids)
            else:
                raise

        # Группировка заявок по departmenttitle
        grouped_tickets = group_tickets_by_department(tickets)
        
        # Подготовка данных для передачи в GNOME Extension
        output = {
            "levels": [
                {
                    "level": department,
                    "value": len(tickets),
                    "details": [
                        {
                            "id": ticket["id"],
                            "subject": ticket["subject"],
                            "userorganization": ticket["userorganization"]
                        }
                        for ticket in tickets
                    ]
                }
                for department, tickets in grouped_tickets.items()
            ],
            "total": sum(len(tickets) for tickets in grouped_tickets.values())
        }

        print(json.dumps(output, ensure_ascii=False, indent=4))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    main()
