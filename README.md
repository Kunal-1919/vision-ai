# VisionAI

**AI-powered image recognition and secure attendance verification** — built with computer vision, face recognition, anti-spoofing, and GPS geofencing.

[![Python](https://img.shields.io/badge/Python-3.14+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.9+-EE4C2C?style=flat&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.10-5C3EE8?style=flat&logo=opencv&logoColor=white)](https://opencv.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> A full-stack AI system that classifies pet images and verifies employee attendance using live face recognition — with fraud prevention for photo spoofing and remote check-ins.

**Author:** [Kunal Santosh Gawade](https://github.com/Kunal-1919) · Full-Stack Developer

---

## Highlights

- **Pet recognition** — Upload a dog or cat image; get instant classification with confidence scores
- **Secure attendance** — Live webcam check-in with identity verification
- **Anti-spoof protection** — Blocks photos, phone screens, and printed image attacks
- **Office geofencing** — Attendance only allowed within configured GPS radius
- **Self-hosted** — Runs locally with no paid third-party AI API dependency
- **Modular architecture** — Separate services for geofence, liveness, face recognition, and classification

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

## How It Works

Attendance verification runs through three security layers. All must pass before check-in is accepted:

```
┌─────────────────────────────────────────────────────────┐
│  1. GEOLOCATION     → Must be inside office geofence    │
│  2. LIVENESS        → Must be a live face (not a photo) │
│  3. FACE MATCH      → Must match an enrolled employee   │
└─────────────────────────────────────────────────────────┘
```

| Attack vector | Protection |
|---------------|------------|
| Photo on phone | Liveness detection (multi-frame analysis) |
| Check-in from home | GPS geofence validation |
| Unknown person | Face embedding mismatch |

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python, FastAPI, Uvicorn |
| **AI / ML** | PyTorch, Torchvision, MobileNetV3-Large |
| **Computer Vision** | OpenCV YuNet, SFace (ONNX), NumPy, Pillow |
| **Security** | Custom liveness detector, Haversine geofencing |
| **Frontend** | HTML5, CSS3, Vanilla JS, MediaDevices & Geolocation APIs |
| **Storage** | JSON file-based (persons, office config) |

### AI Models

| Model | Use case |
|-------|----------|
| MobileNetV3-Large (ImageNet) | Dog / cat classification |
| YuNet ONNX | Face detection |
| SFace ONNX | Face embedding & matching |
| Custom heuristics | Anti-spoof / liveness detection |

---

## Quick Start

### Prerequisites

- Python 3.14+
- Webcam (for attendance)
- Location permission in browser (for geofence)

### Installation

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
./run.sh
```

### Usage

1. **Register Person** — Enroll employees with a clear front-facing photo
2. **Configure office** — Set GPS coordinates in `data/office_location.json`
3. **Attendance Check-in** — Start camera, allow location access, verify attendance
4. **Pet Recognition** — Upload a dog or cat image to classify

---

## Configuration

### Office Geofence (`data/office_location.json`)

```json
{
  "name": "Your Office Name",
  "latitude": 19.17273252804268,
  "longitude": 72.86053980560689,
  "radius_meters": 150,
  "max_accuracy_meters": 100,
  "enabled": true
}
```

Get coordinates from Google Maps → right-click your office → copy lat/lng.

Set `"enabled": false` for local development without geofence.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Service health check |
| `GET` | `/api/attendance/config` | Geofence settings |
| `POST` | `/api/classify/pet` | Classify dog/cat image |
| `POST` | `/api/recognize/face` | Attendance verification (frames + GPS) |
| `GET` | `/api/persons` | List enrolled employees |
| `POST` | `/api/persons/register` | Enroll new employee |
| `GET` | `/api/persons/{id}/photo` | Employee photo |

Interactive API docs: **http://localhost:8088/docs**

---

## Project Structure

```
vision-ai/
├── app/
│   ├── main.py              # FastAPI routes
│   ├── pet_classifier.py    # Dog/cat AI model
│   ├── face_recognizer.py   # Face detection & matching
│   ├── liveness_detector.py # Anti-spoof checks
│   ├── geofence.py          # Office GPS validation
│   └── static/              # Web UI
├── data/
│   ├── office_location.json
│   ├── persons.json
│   ├── known_faces/         # Enrolled photos (gitignored)
│   └── models/              # ONNX models (auto-downloaded)
├── docs/
│   └── CTO_PROJECT_BRIEF.md
├── requirements.txt
├── run.sh
└── LICENSE
```

---

## Documentation

For a detailed technical brief (architecture, security, production recommendations), see [docs/CTO_PROJECT_BRIEF.md](docs/CTO_PROJECT_BRIEF.md).

---

## Roadmap

- [ ] PostgreSQL database for production storage
- [ ] Admin dashboard with attendance reports
- [ ] Docker deployment
- [ ] Mobile app (React Native / Flutter)
- [ ] SSO / LDAP integration

---

## License

MIT © [Kunal Santosh Gawade](https://github.com/Kunal-1919)

---

## Connect

- **GitHub:** [@Kunal-1919](https://github.com/Kunal-1919)
- **Portfolio:** [kunal-gawade-portfolio](https://github.com/Kunal-1919/kunal-gawade-portfolio)
