# VisionAI Enterprise — Biometric Hardware & Device Integration Protocol Specification

**Document Version:** 2.0.0-ENT  
**Security Classification:** Enterprise Public / Architecture Specification  
**System Target:** Enterprise Multimodal Attendance & Access Control Gateway  

---

## 1. Executive Overview

**VisionAI Enterprise** is architected to seamlessly interface with physical biometric hardware terminals (ZKTeco, Hikvision, Suprema, Dahua, Suprema BioStation) as well as Edge AI camera units and mobile apps.

Rather than acting as a standalone single-camera demo, VisionAI provides a **unified biometric gateway** capable of aggregating event logs from physical hardware gates, turnstiles, and biometric wall units into a centralized real-time attendance ledger.

---

## 2. Hardware Compatibility Matrix

VisionAI Enterprise natively supports protocol adapters for industry-standard biometric terminals:

| Vendor / Manufacturer | Terminal Model Series | Communication Protocol | Auth Modes Supported |
|-----------------------|-----------------------|------------------------|----------------------|
| **ZKTeco** | SpeedFace V5L / ProFace X | ADMS / HTTP Push SDK v4.0 | Face, Fingerprint, RFID, Palm |
| **Hikvision** | DS-K1T671M / MinMo Series | ISAPI / HTTP Webhook | 3D Face, QR Code, IC Card |
| **Suprema** | BioStation 3 / FaceStation 2 | BioStar 2 Open API / Wiegand-IP | Multimodal Fusion, Palm Vein |
| **Dahua** | ASA Series Access Terminals | HTTP/JSON Real-time Push | Face Recognition, Fingerprint |
| **VisionAI Edge** | Self-Hosted Linux Edge Nodes | REST API (JSON / HTTPS) | Edge AI Camera + Liveness v2 |

---

## 3. System Architecture & Telemetry Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     PHYSICAL BIOMETRIC HARDWARE                         │
│  ┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐  │
│  │  ZKTeco SpeedFace  │ │ Hikvision MinMo AI │ │ Suprema BioStation │  │
│  │ (Turnstile Gate A) │ │ (R&D Lab Access)   │ │ (Server Room Airlk)│  │
│  └─────────┬──────────┘ └─────────┬──────────┘ └─────────┬──────────┘  │
└────────────┼──────────────────────┼──────────────────────┼──────────────┘
             │                      │                      │
             │ HTTP Push SDK        │ ISAPI Webhook        │ REST API
             ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    VISIONAI ENTERPRISE GATEWAY                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  biometric_webhook() -> Ingestion & Event Deduplication Engine    │  │
│  └─────────────────────────────────┬─────────────────────────────────┘  │
│                                    │                                    │
│  ┌─────────────────────────────────▼─────────────────────────────────┐  │
│  │  Multi-Factor Audit Engine: RBAC + Geofence + Liveness v2 + Match │  │
│  └─────────────────────────────────┬─────────────────────────────────┘  │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                 CENTRAL ATTENDANCE LEDGER & DASHBOARD                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Biometric Webhook & Push SDK API Specification

Physical terminals post authentication events directly to VisionAI Enterprise via the standard ingestion endpoint:

### `POST /api/biometric/webhook`

#### Request Headers
```http
Content-Type: application/json
Authorization: Bearer <ENTERPRISE_GATEWAY_TOKEN>
X-Terminal-Serial: ZK-SF5L-89421
```

#### Request Payload
```json
{
  "device_id": "dev-zk-01",
  "employee_id": "kunal-gawade",
  "auth_mode": "face",
  "status": "success",
  "confidence": 99.4,
  "temperature_celsius": 36.6
}
```

#### Response Payload (`200 OK`)
```json
{
  "sync_status": "accepted",
  "device_id": "dev-zk-01",
  "timestamp": "2026-09-02T15:35:19+00:00",
  "employee_id": "kunal-gawade",
  "auth_mode": "face",
  "verification_status": "success",
  "confidence": 99.4,
  "temperature_celsius": 36.6
}
```

---

## 5. Security & Data Protection Compliance

1. **Template Encryption**: All face embeddings (SFace 128-dimensional floating point vectors) are tokenized and stored locally using AES-256 encrypted storage formats.
2. **GDPR / ISO 27001 Compliance**: Raw facial photos are stored in restricted local volumes (`data/known_faces/`) with strict role-based authorization rules.
3. **No Unencrypted Third-Party Cloud Transmissions**: VisionAI operates 100% on-premises or private cloud, avoiding external API leaks or vendor lock-in.

---

## 6. Device Management API

- `GET /api/biometric/devices` — Returns list of registered hardware terminals and their live operational status (`online`, `standby`, `offline`).
- `POST /api/biometric/devices` — Registers a new physical terminal into the central directory.
- `DELETE /api/biometric/devices/{device_id}` — Unlinks a decommissioned hardware terminal.
