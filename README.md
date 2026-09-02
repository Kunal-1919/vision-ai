# VisionAI Enterprise — Multimodal Biometric & AI Attendance Platform

**Enterprise-Grade Attendance & Access Control Gateway** — Integrates physical biometric hardware terminals (ZKTeco, Hikvision, Suprema, Dahua), Edge AI computer vision, anti-spoofing liveness v2, GPS geofencing, and Role-Based Access Control (RBAC).

[![Python](https://img.shields.io/badge/Python-3.14+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-v2.0.0-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.9+-EE4C2C?style=flat&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.10-5C3EE8?style=flat&logo=opencv&logoColor=white)](https://opencv.org/)
[![Biometric Ready](https://img.shields.io/badge/Biometric-Hardware_Ready-00E5FF?style=flat&logo=hardware&logoColor=white)](#biometric-hardware-integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> A production-ready, zero-cloud-lock-in Enterprise Attendance Engine that bridges physical biometric hardware gates with AI webcam verification, blocking photo spoofing, phone replay fraud, and proxy check-ins.

**Author:** [Kunal Santosh Gawade](https://github.com/Kunal-1919) · Full-Stack & AI Engineer

---

## 🌟 Key Enterprise Highlights

- **Multimodal Biometric Engine**: Native HTTP Push SDK & Webhook ingestion for physical biometric hardware (ZKTeco SpeedFace, Hikvision MinMo, Suprema BioStation, Dahua).
- **5-Layer Security Pipeline**: RBAC Login → GPS Geofence → MobileNetV3 Scene AI → Anti-Spoof Liveness v2 → OpenCV SFace Identity Match.
- **Biometric Device Telemetry**: Real-time health monitoring, IP address tracking, serial number mapping, and terminal unlinking in the admin console.
- **Anti-Spoof Liveness v2**: Detects photo prints, phone screens, digital glare, static replay, and rigid surface motion.
- **Enterprise RBAC**: JWT Bearer auth with identity binding — employees can only check in for their own verified face profile.
- **100% Self-Hosted & On-Premises Ready**: No expensive monthly AI API costs; runs locally or on private cloud infrastructure.

---

## 🛡️ Enterprise Security Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      VERIFICATION & AUDIT PIPELINE                      │
├─────────────────────────────────────────────────────────────────────────┤
│  1. ROLE-BASED ACCESS CONTROL (RBAC)                                    │
│     → Authenticates user JWT session (Admin vs Employee identity binding)│
├─────────────────────────────────────────────────────────────────────────┤
│  2. GPS GEOFENCE VALIDATION                                             │
│     → Haversine distance verification against designated office premises│
├─────────────────────────────────────────────────────────────────────────┤
│  3. SCENE AI ANALYSIS (MobileNetV3)                                     │
│     → Detects mobile phones, screens, or printed photos in frame        │
├─────────────────────────────────────────────────────────────────────────┤
│  4. ANTI-SPOOF LIVENESS DETECTION v2                                    │
│     → FFT screen frequency analysis, color cast, glare, static replay   │
├─────────────────────────────────────────────────────────────────────────┤
│  5. BIOMETRIC FACE MATCH (OpenCV YuNet + SFace)                         │
│     → Extracts 128D face embedding & matches enrolled employee profile   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔌 Biometric Hardware Integration

VisionAI Enterprise is built to connect directly with physical biometric gates and access terminals.

### Supported Protocols & Vendors

| Vendor / Manufacturer | Device Model Series | Communication Protocol | Supported Biometric Modes |
|-----------------------|---------------------|------------------------|---------------------------|
| **ZKTeco** | SpeedFace V5L / ProFace | ADMS / HTTP Push SDK v4.0 | Face, Fingerprint, RFID |
| **Hikvision** | DS-K1T671M / MinMo | ISAPI / HTTP Webhook | 3D Face, QR, Card |
| **Suprema** | BioStation 3 / BioLite | BioStar 2 API / Wiegand-IP | Palm Vein, Fingerprint |
| **Dahua** | ASA Series Terminals | Real-time Push JSON | Face Recognition |

### Hardware Integration Endpoint

Physical hardware terminals post authentication logs directly to:
```http
POST /api/biometric/webhook
Content-Type: application/json
```
```json
{
  "device_id": "dev-zk-01",
  "employee_id": "kunal-gawade",
  "auth_mode": "face",
  "status": "success",
  "confidence": 99.4
}
```

Detailed hardware protocol specification: [`docs/BIOMETRIC_INTEGRATION_SPEC.md`](docs/BIOMETRIC_INTEGRATION_SPEC.md)

---

## 🔐 Role-Based Access Control (RBAC)

| Role | Operational Access |
|------|-------------------|
| **Admin** | Dashboard analytics, attendance logs, employee enrollment & deletion, biometric hardware management |
| **Employee** | Attendance camera check-in (restricted strictly to own enrolled identity) |

### Default Admin Credentials (First Run)
- **Username:** `admin`
- **Password:** `Admin@123`

---

## ⚡ Quick Start & Deployment

```bash
# 1. Clone repository
git clone https://github.com/Kunal-1919/vision-ai.git
cd vision-ai

# 2. Setup environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Launch application server
./run.sh
```

Navigate to **http://localhost:8088** in your browser.  
Interactive OpenAPI / Swagger Documentation: **http://localhost:8088/docs**

---

## 📊 Complete REST API Reference

| Method | Endpoint | Authorization | Description |
|--------|----------|---------------|-------------|
| `POST` | `/api/auth/login` | Public | Authenticate user & issue JWT |
| `GET` | `/api/auth/me` | Auth Bearer | Fetch current user session profile |
| `GET` | `/api/attendance/stats` | Admin | Aggregate dashboard analytics |
| `GET` | `/api/attendance/logs` | Admin | Retrieve recent check-in audit logs |
| `POST` | `/api/recognize/face` | Employee | Submit live camera frames for attendance |
| `GET` | `/api/persons` | Admin | List all enrolled employees |
| `POST` | `/api/persons/register` | Admin | Enroll new employee & generate credentials |
| `DELETE`| `/api/persons/{id}` | Admin | Unenroll employee & delete credentials |
| `GET` | `/api/biometric/devices` | Admin | List connected biometric hardware terminals |
| `POST` | `/api/biometric/devices` | Admin | Register physical biometric terminal |
| `DELETE`| `/api/biometric/devices/{id}`| Admin | Unlink biometric terminal |
| `POST` | `/api/biometric/webhook` | Webhook | Hardware terminal event stream listener |

---

## 📁 Repository Architecture

```
vision-ai/
├── app/
│   ├── main.py                  # FastAPI application routes & exception handlers
│   ├── auth.py                  # JWT authentication, password hashing & RBAC
│   ├── biometric.py             # Enterprise biometric hardware manager
│   ├── face_recognizer.py       # OpenCV YuNet face detector & SFace recognizer
│   ├── liveness_detector.py     # Anti-spoofing multi-frame analysis v2
│   ├── scene_validator.py       # PyTorch MobileNetV3 device detection
│   ├── geofence.py              # Haversine GPS office boundary validator
│   ├── attendance_logger.py     # Attendance transaction logger
│   └── static/                  # Glassmorphism HTML5/CSS3 frontend app
├── data/                        # Local database storage & model weights
├── docs/                        # Specifications & architectural blueprints
│   ├── BIOMETRIC_INTEGRATION_SPEC.md
│   └── CTO_PROJECT_BRIEF.md
└── requirements.txt
```

---

## 📄 License & Credits

Built by **[Kunal Santosh Gawade](https://github.com/Kunal-1919)** — Licensed under the MIT License.
