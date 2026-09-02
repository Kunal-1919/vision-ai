# VisionAI — Project Brief for CTO

## Executive Summary

**VisionAI** is an AI-powered image recognition and secure attendance verification system built for organizational use. It combines computer vision, face recognition, anti-spoofing (liveness detection), and GPS-based geofencing to ensure employees can only mark attendance when they are physically present at the office with a live face — not via photos, phone screens, or remote check-ins from home.

The system runs as a self-hosted web application with no dependency on paid third-party AI APIs for core recognition logic.

---

## Business Problem

Traditional attendance systems are vulnerable to:

| Threat | Example |
|--------|---------|
| **Identity spoofing** | Employee shows a photo on a phone to the camera |
| **Remote check-in** | Employee marks attendance from home |
| **Proxy attendance** | Someone else checks in on behalf of a colleague |

VisionAI addresses these with a **three-layer verification pipeline** before attendance is accepted.

---

## Core Capabilities

### 1. Pet Image Recognition
- Upload a dog or cat image
- System classifies the animal and returns label + confidence score
- Built as a demonstration of general image classification capability

### 2. Secure Attendance Check-in
- Live webcam-based face verification
- Employee enrollment with photo and profile details
- Multi-step fraud prevention before attendance is recorded

### 3. Employee Registration
- Enroll employees with name, role, department, email, and face photo
- Face embeddings are generated and stored for future matching

---

## Security Architecture (Attendance)

Attendance is only accepted when **all three checks pass**:

```
┌─────────────────────────────────────────────────────────────┐
│                    ATTENDANCE CHECK-IN                       │
├─────────────────────────────────────────────────────────────┤
│  1. GEOLOCATION CHECK                                        │
│     → User must be within office premises (GPS geofence)     │
│     → Rejects home / remote check-ins                        │
├─────────────────────────────────────────────────────────────┤
│  2. LIVENESS / ANTI-SPOOF CHECK                              │
│     → Captures 4 live camera frames                          │
│     → Detects photos, phone screens, printed images          │
│     → Blocks static replay and screen-based attacks          │
├─────────────────────────────────────────────────────────────┤
│  3. FACE RECOGNITION                                         │
│     → Matches live face against enrolled employees           │
│     → Returns identity + employee details on success         │
└─────────────────────────────────────────────────────────────┘
```

If any layer fails, the system returns a **Restricted Activity** response and attendance is not marked.

---

## Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.14+ | Core runtime |
| **FastAPI** | 0.115.6 | REST API framework |
| **Uvicorn** | 0.34.0 | ASGI web server |
| **python-multipart** | 0.0.20 | File upload handling |

### AI / Machine Learning

| Technology | Purpose |
|------------|---------|
| **PyTorch** | Deep learning inference engine |
| **Torchvision** | Pre-trained model loading |
| **MobileNetV3-Large** | Dog/cat image classification (ImageNet weights) |
| **OpenCV YuNet** | Face detection (ONNX model) |
| **OpenCV SFace** | Face recognition / embedding extraction (ONNX model) |
| **Custom Liveness Detector** | Anti-spoofing heuristics (screen pattern, glare, texture, motion) |

### Image Processing

| Technology | Purpose |
|------------|---------|
| **OpenCV (contrib)** | Face detection, alignment, feature extraction, image analysis |
| **Pillow (PIL)** | Image validation and preprocessing |
| **NumPy** | Numerical operations for ML and liveness checks |

### Frontend

| Technology | Purpose |
|------------|---------|
| **HTML5** | Application structure |
| **CSS3** | UI styling (modern dark theme) |
| **Vanilla JavaScript** | Camera access, geolocation, API calls |
| **MediaDevices API** | Webcam capture for live frames |
| **Geolocation API** | GPS coordinates for office geofence validation |

### Data Storage

| Storage | Format | Contents |
|---------|--------|----------|
| `data/persons.json` | JSON | Employee profiles (name, role, email, department) |
| `data/known_faces/` | JPG images | Enrolled employee face photos |
| `data/office_location.json` | JSON | Office GPS coordinates and geofence radius |
| `data/models/` | ONNX files | Downloaded face detection/recognition models |

> **Note:** Current version uses file-based storage. Suitable for pilot/R&D. Production deployment should migrate to a database (PostgreSQL/MongoDB) with encrypted face embeddings.

---

## AI Models in Detail

### Pet Classification — MobileNetV3-Large
- **Source:** PyTorch Torchvision pre-trained weights (ImageNet)
- **Input:** Uploaded image (any common format)
- **Output:** `dog`, `cat`, or `unknown` with confidence percentage
- **How it works:** Runs inference on 1000 ImageNet classes, maps dog/cat breed labels to final classification

### Face Detection — YuNet (2023)
- **Source:** OpenCV Zoo ONNX model
- **Model file:** `face_detection_yunet_2023mar.onnx`
- **Purpose:** Detects face bounding box in camera frames and enrollment photos

### Face Recognition — SFace (2021)
- **Source:** OpenCV Zoo ONNX model
- **Model file:** `face_recognition_sface_2021dec.onnx`
- **Purpose:** Generates 128-dimensional face embeddings for identity matching
- **Matching:** Cosine similarity against enrolled employee embeddings

### Liveness Detection — Custom Module
- **Type:** Rule-based + signal processing (no external API)
- **Signals analyzed:**
  - Screen moiré / pixel grid patterns (FFT analysis)
  - Display color cast (blue-heavy screen emission)
  - Specular glare (phone screen reflections)
  - Flat texture (printed/screen surfaces vs real skin)
  - Static replay (identical frames across captures)
  - Rigid surface motion (phone held as single object)
- **Input:** 4 consecutive live camera frames
- **Output:** Live / Spoof decision with spoof score

### Geofencing — Custom Module
- **Algorithm:** Haversine distance formula
- **Validation:** Server-side (client cannot bypass)
- **Current office:** Leap India Office
  - Latitude: `19.17273252804268`
  - Longitude: `72.86053980560689`
  - Allowed radius: `150 meters`
  - Max GPS accuracy: `100 meters`

---

## System Architecture

```
┌──────────────┐         HTTPS/HTTP          ┌──────────────────────────┐
│   Browser    │ ◄──────────────────────────► │      FastAPI Server      │
│  (Frontend)  │                              │       (Uvicorn)          │
│              │  • Camera frames (x4)         │                          │
│  • Webcam    │  • GPS lat/lng/accuracy     │  ┌────────────────────┐  │
│  • GPS       │  • Image uploads              │  │  GeofenceValidator │  │
│  • UI        │                               │  └────────────────────┘  │
└──────────────┘                               │  ┌────────────────────┐  │
                                               │  │ LivenessDetector   │  │
                                               │  └────────────────────┘  │
                                               │  ┌────────────────────┐  │
                                               │  │  FaceRecognizer    │  │
                                               │  └────────────────────┘  │
                                               │  ┌────────────────────┐  │
                                               │  │  PetClassifier     │  │
                                               │  └────────────────────┘  │
                                               └───────────┬──────────────┘
                                                           │
                                               ┌───────────▼──────────────┐
                                               │      Local Data Store     │
                                               │  persons.json             │
                                               │  known_faces/             │
                                               │  office_location.json     │
                                               │  models/ (ONNX)           │
                                               └──────────────────────────┘
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Service health check |
| `GET` | `/api/attendance/config` | Office geofence settings (name, radius) |
| `POST` | `/api/classify/pet` | Classify dog/cat from uploaded image |
| `POST` | `/api/recognize/face` | Attendance verification (frames + GPS) |
| `GET` | `/api/persons` | List enrolled employees |
| `POST` | `/api/persons/register` | Enroll new employee with face photo |
| `GET` | `/api/persons/{id}/photo` | Get enrolled employee photo |

### Attendance API Request (simplified)
```
POST /api/recognize/face
Content-Type: multipart/form-data

files: [frame-0.jpg, frame-1.jpg, frame-2.jpg, frame-3.jpg]
latitude: 19.17273252804268
longitude: 72.86053980560689
accuracy_meters: 15
```

### Restricted Response (example — outside office)
```json
{
  "recognized": false,
  "restricted": true,
  "location_verified": false,
  "message": "This activity is restricted. Attendance can only be marked from the office premises..."
}
```

---

## Project Structure

```
RnD_project/
├── app/
│   ├── main.py                 # FastAPI app & API routes
│   ├── config.py               # App configuration & thresholds
│   ├── pet_classifier.py       # Dog/cat AI classification
│   ├── face_recognizer.py      # Face detection & matching
│   ├── liveness_detector.py    # Anti-spoof / liveness checks
│   ├── geofence.py             # Office GPS geofencing
│   └── static/
│       ├── index.html          # Web UI
│       ├── style.css           # Styling
│       └── app.js              # Frontend logic
├── data/
│   ├── persons.json            # Employee registry
│   ├── office_location.json    # Office GPS config
│   ├── known_faces/            # Employee face photos
│   └── models/                 # Downloaded ONNX models
├── requirements.txt            # Python dependencies
├── run.sh                      # One-command startup script
└── README.md                   # Developer setup guide
```

---

## How to Run

```bash
cd RnD_project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

Application URL: **http://localhost:8088**

---

## Current Status & Validated Scenarios

| Scenario | Result |
|----------|--------|
| Upload dog image | Correctly identified as dog |
| Upload cat image | Correctly identified as cat |
| Live face at office | Attendance verified |
| Photo on phone shown to camera | **Blocked** (anti-spoof) |
| Check-in from home / remote location | **Blocked** (geofence) |
| Employee not enrolled | Rejected (no match) |

---

## Production Readiness & Recommendations

The current build is a **functional R&D / pilot** system. For enterprise production deployment, we recommend:

1. **Database** — Replace JSON file storage with PostgreSQL or MongoDB
2. **HTTPS** — Deploy behind Nginx/Apache with SSL certificates
3. **Authentication** — Add employee login (SSO/LDAP) before attendance
4. **Audit logs** — Record every check-in attempt with timestamp, location, result
5. **Admin dashboard** — Manage employees, view attendance reports, configure geofence
6. **Mobile app** — Native iOS/Android for better GPS accuracy and camera control
7. **Cloud deployment** — AWS / Azure / GCP with Docker containerization
8. **Data privacy** — Encrypt face embeddings at rest; comply with local data protection laws

---

## Key Differentiators

- **Runs locally** — No per-request cost on external AI APIs
- **Multi-layer fraud prevention** — Geofence + Liveness + Face match
- **Modular architecture** — Each security layer is a separate, testable module
- **Configurable office location** — Easy to update via `office_location.json`
- **Extensible** — Can add fingerprint, QR code, or hardware-based liveness in future

---

## Team & Timeline

| Item | Detail |
|------|--------|
| **Project name** | VisionAI |
| **Version** | 1.1.0 |
| **Environment** | Python 3.14, macOS (development) |
| **Deployment port** | 8088 |
| **Organization** | Leap India (pilot deployment) |
| **Author** | [Kunal Santosh Gawade](https://github.com/Kunal-1919) |
| **Repository** | [github.com/Kunal-1919/vision-ai](https://github.com/Kunal-1919/vision-ai) |

---

*Document for technical review. For setup instructions, see [README.md](../README.md).*
