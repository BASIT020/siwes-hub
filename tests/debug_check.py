"""Small debugging script for the pending-logs / notification / students issues."""
import requests

BASE = "http://127.0.0.1:8000"
PASSWORD = "Demo#2026!"


def login(username):
    s = requests.Session()
    s.get(f"{BASE}/api/auth/csrf/")
    token = s.cookies.get("csrftoken")
    s.post(f"{BASE}/api/auth/login/", json={"username": username, "password": PASSWORD},
           headers={"X-CSRFToken": token, "Referer": BASE})
    return s


sup = login("chioma.eze")
r = sup.get(f"{BASE}/api/logs/?status=submitted")
print("SUPervisor pending status:", r.status_code)
data = r.json()
print(json_pending := len(data) if isinstance(data, list) else len(data.get("results", [])))
print([ (l["id"], l["student_name"], l["log_date"], l["status"]) for l in (data if isinstance(data, list) else data.get("results", [])) ][:10])

admin = login("admin_siwes")
stu = admin.get(f"{BASE}/api/students/")
print("students status:", stu.status_code)
data = stu.json()
students = data if isinstance(data, list) else data.get("results", [])
print([ (s["id"], s["matric_number"], s["full_name"]) for s in students ])

st = login("student1")
n = st.get(f"{BASE}/api/notifications/")
print("notifications status:", n.status_code)
data = n.json()
notifs = data if isinstance(data, list) else data.get("results", [])
print("count:", len(notifs))
print([(x.get("kind"), x.get("title")) for x in notifs][:8])
