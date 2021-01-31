# script for checking https certificate expiration and notification
from typing import List, Tuple
from datetime import datetime
import json
from urllib.request import socket, ssl, urlopen, Request


WEBHOOK = "https://hooks.slack.com/services/..."
HOSTS = [
    # PROD
    ("app.ru", 443),
]

context = ssl.create_default_context()


def get_date(hostname, port):
    with socket.create_connection((hostname, port)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
            date_expire = datetime.strptime(cert["notAfter"], "%b  %d %H:%M:%S %Y %Z")
            return date_expire


def check_certs(hosts: List[Tuple[str, int]]) -> List[str]:
    now = datetime.now()
    exc_alerts = []
    aware_alerts = []
    critical_alerts = []
    expired_alerts = []
    for host, port in hosts:
        try:
            date_expire = get_date(host, port)
        except Exception as ex:
            exc_alerts.append(f"💩 *`{host}`* check failed. Details:\n  {str(ex)}")
            continue
        delta = date_expire - now
        if delta.days >= 14:
            aware_alerts.append(f"📜 *`{host}`* certificate expires in *{delta.days}* days.")
        if 7 <= delta.days < 14:
            critical_alerts.append(f"🧨 *`{host}`* certificate expires in *{delta.days}* days.")
        if delta.days < 0:
            expired_alerts.append(f"☠️ *`{host}`* certificate expired.")
    return expired_alerts + critical_alerts + aware_alerts + exc_alerts


def send_alerts(alerts: List[str]):
    attachment = {
        "username": "Kate Certificate Watchbee",
        "icon_emoji": ":bee:",
        "attachments": [
            {
                "color": "#f2c744",
                "pretext": "*bzZ BZZ mazafaka*",
                "text": '\n'.join(alerts),
            },
        ]
    }
    try:
        urlopen(
            Request(
                WEBHOOK,
                data=json.dumps(attachment).encode(),
                headers={"content-type": "application/json"}
            )
        )
    except Exception:
        ...


if __name__ == "__main__":
    alerts = check_certs(HOSTS)
    if alerts:
        send_alerts(alerts)
