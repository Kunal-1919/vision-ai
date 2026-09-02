# VisionAI

**AI-powered secure attendance system** — live face verification, anti-spoofing, phone detection, GPS geofencing, and an admin dashboard.

[![Python](https://img.shields.io/badge/Python-3.14+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.9+-EE4C2C?style=flat&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.10-5C3EE8?style=flat&logo=opencv&logoColor=white)](https://opencv.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Enterprise-grade attendance check-in that blocks photo spoofing, phone-in-frame fraud, and remote check-ins from home.

**Author:** [Kunal Santosh Gawade](https://github.com/Kunal-1919) · Full-Stack Developer

---

## Highlights

- **4-layer security pipeline** — Geofence → Scene AI → Liveness → Face Match
- **Phone/device detection** — MobileNet scene analysis blocks phones in camera frame
- **Anti-spoof liveness** — Detects photos, screens, and static replays
- **Office geofencing** — GPS validation; no check-in from home
- **Attendance dashboard** — Live stats, blocked attempt breakdown, activity log
- **Self-hosted** — No paid third-party AI APIs

---

## RBAC — Role-Based Access Control

| Role | Access |
|------|--------|
| **Admin** | Dashboard, attendance logs, enroll employees, create login credentials |
| **Employee** | Mark own attendance only (face must match logged-in account) |

### Default admin credentials (first run)

- **Username:** `admin`
- **Password:** `Admin@123`

Change the password in production. Set `VISIONAI_JWT_SECRET` environment variable for production JWT signing.

### Employee enrollment flow

1. Admin signs in
2. Goes to **Enroll Employee**
3. Uploads face photo + sets username/password
4. Employee signs in with those credentials to mark attendance

---

## Security Pipeline

```
┌─────────────────────────────────────────────────────────┐
│  1. GEOLOCATION     → Must be inside office geofence    │
│  2. SCENE AI        → No phones/devices in camera frame │
│  3. LIVENESS        → Must be a live face (not a photo) │
│  4. FACE MATCH      → Must match an enrolled employee   │
└─────────────────────────────────────────────────────────┘
```

| Attack vector | Protection |
|---------------|------------|
| Photo on phone | Liveness + Scene AI (phone detection) |
| Check-in from home | GPS geofence |
| Phone held to camera | Scene AI device detection |
| Unknown person | Face embedding mismatch |

---

## Demo

```bash
git clone https://github.com/Kunal-1919/vision-ai.git
cd vision-ai
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

Open **http://localhost:8088**

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python, FastAPI, Uvicorn |
| **AI / ML** | PyTorch, MobileNetV3-Large, OpenCV YuNet, SFace ONNX |
| **Security** | Custom liveness detector, scene validator, Haversine geofencing |
| **Frontend** | HTML5, CSS3, Vanilla JS, MediaDevices & Geolocation APIs |
| **Storage** | JSON (persons, attendance logs, office config) |

---

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

### Usage

1. **Dashboard** — View attendance stats and recent activity
2. **Register Person** — Enroll employees with face photos
3. **Attendance Check-in** — Live camera verification at the office

Configure office GPS in `data/office_location.json`.

---

## API Endpoints

| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| `POST` | `/api/auth/login` | Public | Sign in |
| `GET` | `/api/auth/me` | Auth | Current user |
| `GET` | `/api/attendance/stats` | Admin | Dashboard statistics |
| `GET` | `/api/attendance/logs` | Admin | Attendance records |
| `GET` | `/api/users` | Admin | List system users |
| `POST` | `/api/recognize/face` | Employee | Mark attendance |
| `POST` | `/api/persons/register` | Admin | Enroll employee + login |

API docs: **http://localhost:8088/docs**

---

## Project Structure

```
vision-ai/
├── app/
│   ├── main.py
│   ├── scene_validator.py      # AI phone/device detection
│   ├── liveness_detector.py    # Anti-spoof checks
│   ├── face_recognizer.py      # Face matching
│   ├── geofence.py             # GPS validation
│   ├── attendance_logger.py    # Check-in logging
│   └── static/
├── data/
│   ├── attendance_log.json
│   ├── office_location.json
│   └── persons.json
└── docs/CTO_PROJECT_BRIEF.md
```

---

## License

MIT © [Kunal Santosh Gawade](https://github.com/Kunal-1919)
