# VisionAI Enterprise — Technical Project Brief for CTO & Engineering Leadership

## Executive Summary

**VisionAI Enterprise** is an enterprise-grade, multimodal biometric attendance platform and security access gateway. It unifies physical biometric hardware access terminals (ZKTeco, Hikvision, Suprema, Dahua) with Edge AI computer vision, anti-spoofing liveness detection (v2), GPS geofencing, and Role-Based Access Control (RBAC).

Built with Python, FastAPI, PyTorch, and OpenCV, VisionAI operates 100% self-hosted on-premises or on private cloud infrastructure with **zero dependency on paid third-party AI cloud services**.

---

## 1. Enterprise Business Problem & Security Threat Vectors

Legacy attendance check-in systems and basic webcam solutions fail under modern security audits due to key attack vectors:

| Threat Vector | Real-World Attack Scenario | VisionAI Enterprise Countermeasure |
|---------------|----------------------------|-----------------------------------|
| **Identity Replay Spoofing** | Displaying a colleague's photo on a smartphone screen | Multi-frame FFT pattern analysis, specular glare scoring & PyTorch MobileNet scene device detection |
| **Proxy Attendance** | An employee marking attendance on behalf of another user | JWT RBAC identity binding — user can only mark attendance matching their own logged-in account |
| **Remote Location Fraud** | Marking attendance from home or outside the office | Haversine GPS geofencing requiring physical office presence with accuracy validation |
| **Hardware Isolation** | Physical gate turnstiles operating in silos without central reporting | Integrated Biometric Device Manager API + HTTP Push SDK Event Listener Gateway |

---

## 2. 5-Layer Defense-in-Depth Security Pipeline

Every attendance transaction must sequentially pass 5 independent security controls before being logged as verified:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      5-LAYER ENTERPRISE SECURITY PIPELINE                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. ROLE-BASED ACCESS CONTROL (RBAC)                                        │
│     → Validates JWT bearer token, active session, and employee account ID   │
├─────────────────────────────────────────────────────────────────────────────┤
│  2. GEOLOCATION GEOFENCE VALIDATION                                         │
│     → Validates user GPS coordinates against office latitude/longitude      │
├─────────────────────────────────────────────────────────────────────────────┤
│  3. SCENE AI ANALYSIS (MobileNetV3)                                         │
│     → Detects presence of smartphones, tablets, or printed photos in frame  │
├─────────────────────────────────────────────────────────────────────────────┤
│  4. ANTI-SPOOF LIVENESS DETECTION (v2 Multi-Heuristic)                      │
│     → Evaluates FFT screen frequency, color cast, glare, and static replay  │
├─────────────────────────────────────────────────────────────────────────────┤
│  5. BIOMETRIC FACE RECOGNITION (YuNet + SFace ONNX Engine)                  │
│     → Extracts 128D facial feature embedding & matches enrolled profile     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Multimodal Biometric Hardware Integration Engine

VisionAI Enterprise includes a native **Biometric Hardware Integration Gateway** (`app/biometric.py`), enabling physical access hardware terminals to stream real-time authentication logs directly into the central enterprise ledger.

### Supported Hardware Terminal Protocols

- **ZKTeco ADMS / Push SDK v4.0** (SpeedFace, ProFace series)
- **Hikvision ISAPI / HTTP Webhook Ingestion** (DS-K1T671M series)
- **Suprema BioStar 2 API** (BioStation 3, FaceStation)
- **Wiegand-over-IP Gateway Bridges**

### Biometric Device Management Features
- Live terminal status tracking (`online`, `standby`, `offline`)
- Hardware serial number, IP address, and physical location binding
- Terminal unlinking and security audit logging

---

## 4. Technical Architecture & Component Breakdown

| Layer | Component | Technical Implementation |
|-------|-----------|--------------------------|
| **API Framework** | FastAPI + Uvicorn | Async ASGI engine with Pydantic validation & custom HTTP exception middleware |
| **Authentication** | PyJWT + PBKDF2-HMAC-SHA256 | High-iteration salted password hashing with Bearer & query parameter token support |
| **Face Detection** | OpenCV YuNet (ONNX) | Fast multi-scale face detector |
| **Face Recognition** | OpenCV SFace (ONNX) | Cosine similarity feature matcher over 128D embeddings |
| **Scene Validation** | PyTorch MobileNetV3-Large | Real-time object classification targeting screens, phones, and print media |
| **Liveness v2** | Custom Signal Processing | FFT spectrum grid energy, specular glare clustering, color cast variance |
| **Hardware Sync** | BiometricManager Gateway | Device telemetry registry & HTTP Push SDK webhook listener |

---

## 5. Deployment & Enterprise Scalability

VisionAI Enterprise is designed for straightforward containerized and on-premises deployment:

- **Docker Containerization**: Multi-stage build support with OpenCV & PyTorch dependencies.
- **On-Premises Privacy**: 100% data residency; facial embeddings and photos remain strictly inside local networks.
- **RESTful Integration**: OpenAPI 3.0 compatible endpoints (`/docs`) for easy integration with enterprise HRIS, ZingHR, SAP, or Active Directory / LDAP servers.
