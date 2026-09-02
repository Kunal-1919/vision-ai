const state = {
  cameraStream: null,
  attendanceConfig: null,
  lastPosition: null,
};

const FRAME_COUNT = 4;
const FRAME_INTERVAL_MS = 220;

const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");
const healthStatus = document.getElementById("healthStatus");

const REASON_LABELS = {
  geofence: "Outside office",
  scene: "Phone / device detected",
  liveness: "Spoof detected",
  face_mismatch: "Face not recognized",
  verified: "Verified",
};

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((item) => item.classList.remove("active"));
    panels.forEach((panel) => panel.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(`${tab.dataset.tab}-panel`).classList.add("active");
    if (tab.dataset.tab === "dashboard") loadDashboard();
  });
});

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("Service unavailable");
    healthStatus.textContent = "Service online";
    healthStatus.classList.add("ok");
  } catch (error) {
    healthStatus.textContent = "Service offline";
    healthStatus.classList.add("error");
  }
}

function setLoading(button, isLoading, label = "Processing...") {
  if (!button) return;
  button.disabled = isLoading;
  button.dataset.originalText = button.dataset.originalText || button.textContent;
  button.textContent = isLoading ? label : button.dataset.originalText;
}

function formatTime(isoString) {
  if (!isoString) return "—";
  const date = new Date(isoString);
  return date.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

async function loadDashboard() {
  try {
    const [statsRes, logsRes] = await Promise.all([
      fetch("/api/attendance/stats"),
      fetch("/api/attendance/logs?limit=15"),
    ]);
    const stats = await statsRes.json();
    const logs = await logsRes.json();

    document.getElementById("statEnrolled").textContent = stats.enrolled_count ?? 0;
    document.getElementById("statCheckins").textContent = stats.check_ins_today ?? 0;
    document.getElementById("statBlocked").textContent = stats.blocked_today ?? 0;
    document.getElementById("statTotal").textContent = stats.total_check_ins ?? 0;

    const reasonsEl = document.getElementById("blockedReasons");
    const reasons = stats.blocked_reasons_today || {};
    const reasonKeys = Object.keys(reasons);
    if (!reasonKeys.length) {
      reasonsEl.innerHTML = '<p class="muted">No blocked attempts today.</p>';
    } else {
      reasonsEl.innerHTML = reasonKeys.map((key) => `
        <div class="reason-item">
          <span>${REASON_LABELS[key] || key}</span>
          <strong>${reasons[key]}</strong>
        </div>
      `).join("");
    }

    const tbody = document.getElementById("attendanceLogBody");
    if (!logs.logs?.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="muted">No attendance records yet.</td></tr>';
      return;
    }

    tbody.innerHTML = logs.logs.map((log) => `
      <tr class="${log.status}">
        <td>${formatTime(log.timestamp)}</td>
        <td>${log.person_name || "—"}</td>
        <td><span class="status-chip ${log.status}">${log.status}</span></td>
        <td>${REASON_LABELS[log.reason] || log.reason}</td>
        <td>${log.message}</td>
      </tr>
    `).join("");
  } catch (error) {
    document.getElementById("attendanceLogBody").innerHTML =
      `<tr><td colspan="5" class="muted">Unable to load dashboard: ${error.message}</td></tr>`;
  }
}

function renderFaceResult(data) {
  document.getElementById("faceResultEmpty").classList.add("hidden");
  const content = document.getElementById("faceResultContent");
  const restrictedBanner = document.getElementById("restrictedBanner");
  const personCard = document.getElementById("personCard");

  content.classList.remove("hidden");
  restrictedBanner.classList.add("hidden");
  personCard.classList.add("hidden");
  content.classList.remove("success");

  if (data.restricted) {
    restrictedBanner.classList.remove("hidden");
    document.getElementById("restrictedMessage").textContent = data.message;
    document.getElementById("faceMessage").textContent = "";
    document.getElementById("faceConfidence").textContent = "";
    loadDashboard();
    return;
  }

  if (data.recognized && data.person) {
    personCard.classList.remove("hidden");
    content.classList.add("success");
    document.getElementById("personName").textContent = data.person.name;
    document.getElementById("personRole").textContent = data.person.role || "Role not set";
    document.getElementById("personDepartment").textContent = data.person.department || "";
    document.getElementById("personEmail").textContent = data.person.email || "";
    document.getElementById("personNotes").textContent = data.person.notes || "";
    document.getElementById("personPhoto").src = `${data.person.photo_url}?t=${Date.now()}`;
  }

  document.getElementById("faceMessage").textContent = data.message;
  const details = [];
  if (data.office_name && data.distance_meters != null) {
    details.push(`Distance from ${data.office_name}: ${Math.round(data.distance_meters)}m`);
  }
  if (data.confidence) details.push(`Match confidence: ${data.confidence}%`);
  document.getElementById("faceConfidence").textContent = details.join(" • ");
  loadDashboard();
}

async function recognizeFaceFrames(blobs, position) {
  const formData = new FormData();
  blobs.forEach((blob, index) => {
    formData.append("files", blob, `frame-${index}.jpg`);
  });

  if (position) {
    formData.append("latitude", String(position.coords.latitude));
    formData.append("longitude", String(position.coords.longitude));
    formData.append("accuracy_meters", String(position.coords.accuracy));
  }

  const response = await fetch("/api/recognize/face", { method: "POST", body: formData });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Recognition failed");
  renderFaceResult(data);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const startCameraBtn = document.getElementById("startCameraBtn");
const captureFaceBtn = document.getElementById("captureFaceBtn");
const cameraVideo = document.getElementById("cameraVideo");
const cameraCanvas = document.getElementById("cameraCanvas");
const captureHint = document.getElementById("captureHint");
const locationStatus = document.getElementById("locationStatus");
const locationStatusText = document.getElementById("locationStatusText");

function setLocationStatus(mode, text) {
  locationStatus.classList.remove("ready", "warning", "error");
  if (mode) locationStatus.classList.add(mode);
  locationStatusText.textContent = text;
}

function getCurrentPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation is not supported on this device."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => resolve(position),
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          reject(new Error("Location permission denied. Attendance requires office location access."));
        } else if (error.code === error.POSITION_UNAVAILABLE) {
          reject(new Error("Unable to determine your location. Please try again at the office."));
        } else {
          reject(new Error("Location request timed out. Please try again."));
        }
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  });
}

async function loadAttendanceConfig() {
  try {
    const response = await fetch("/api/attendance/config");
    if (!response.ok) throw new Error("Unable to load attendance settings");
    state.attendanceConfig = await response.json();
    if (!state.attendanceConfig.enabled) {
      setLocationStatus("warning", "Office geofence is currently disabled.");
      return;
    }
    setLocationStatus(
      null,
      `Attendance allowed only within ${state.attendanceConfig.radius_meters}m of ${state.attendanceConfig.office_name}.`,
    );
  } catch (error) {
    setLocationStatus("error", error.message);
  }
}

async function verifyOfficeLocation() {
  if (state.attendanceConfig && !state.attendanceConfig.enabled) return null;
  setLocationStatus("warning", "Checking your office location...");
  const position = await getCurrentPosition();
  state.lastPosition = position;
  const { accuracy } = position.coords;
  if (state.attendanceConfig && accuracy > state.attendanceConfig.max_accuracy_meters) {
    throw new Error(
      `Location accuracy is too low (${Math.round(accuracy)}m). Move near a window or enable precise location.`,
    );
  }
  setLocationStatus("ready", `Location captured with ${Math.round(accuracy)}m accuracy.`);
  return position;
}

startCameraBtn.addEventListener("click", async () => {
  try {
    if (state.cameraStream) state.cameraStream.getTracks().forEach((t) => t.stop());
    state.cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user" }, audio: false,
    });
    cameraVideo.srcObject = state.cameraStream;
    captureFaceBtn.disabled = false;
    captureHint.textContent = "Camera ready. Keep phones out of frame, then verify attendance.";
  } catch {
    alert("Unable to access camera. Please allow camera permission.");
  }
});

captureFaceBtn.addEventListener("click", async () => {
  const width = cameraVideo.videoWidth;
  const height = cameraVideo.videoHeight;
  if (!width || !height) { alert("Camera is not ready yet."); return; }

  cameraCanvas.width = width;
  cameraCanvas.height = height;
  const context = cameraCanvas.getContext("2d");

  setLoading(captureFaceBtn, true, "Checking location...");
  captureHint.textContent = "Verifying office location...";

  try {
    const position = await verifyOfficeLocation();
    setLoading(captureFaceBtn, true, "Verifying live face...");
    captureHint.textContent = "Running AI scene analysis and liveness checks...";

    const blobs = [];
    for (let i = 0; i < FRAME_COUNT; i += 1) {
      context.drawImage(cameraVideo, 0, 0, width, height);
      blobs.push(await new Promise((r) => cameraCanvas.toBlob(r, "image/jpeg", 0.92)));
      if (i < FRAME_COUNT - 1) await sleep(FRAME_INTERVAL_MS);
    }
    await recognizeFaceFrames(blobs, position);
    captureHint.textContent = "Verification complete.";
  } catch (error) {
    setLocationStatus("error", error.message);
    renderFaceResult({ restricted: true, recognized: false, message: error.message });
    captureHint.textContent = "Verification failed.";
  } finally {
    setLoading(captureFaceBtn, false);
  }
});

async function loadPersons() {
  const container = document.getElementById("personList");
  try {
    const response = await fetch("/api/persons");
    const data = await response.json();
    container.innerHTML = "";
    if (!data.persons.length) {
      container.innerHTML = '<p class="muted">No people enrolled yet.</p>';
      return;
    }
    const template = document.getElementById("personListItemTemplate");
    data.persons.forEach((person) => {
      const node = template.content.cloneNode(true);
      node.querySelector("img").src = `${person.photo_url}?t=${Date.now()}`;
      node.querySelector("h3").textContent = person.name;
      node.querySelector(".role").textContent = person.role || "Role not set";
      node.querySelector(".department").textContent = person.department || "";
      container.appendChild(node);
    });
  } catch {
    container.innerHTML = '<p class="muted">Unable to load enrolled people.</p>';
  }
}

const registerForm = document.getElementById("registerForm");
const registerPhoto = document.getElementById("registerPhoto");
const registerPhotoLabel = document.getElementById("registerPhotoLabel");

registerPhoto.addEventListener("change", () => {
  const file = registerPhoto.files?.[0];
  registerPhotoLabel.textContent = file ? file.name : "Upload a clear front-facing photo";
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = registerForm.querySelector("button[type='submit']");
  const formData = new FormData(registerForm);
  setLoading(submitButton, true, "Registering...");
  try {
    const response = await fetch("/api/persons/register", { method: "POST", body: formData });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Registration failed");
    registerForm.reset();
    registerPhotoLabel.textContent = "Upload a clear front-facing photo";
    await loadPersons();
    await loadDashboard();
    alert(`Registered ${data.person.name} successfully.`);
  } catch (error) {
    alert(error.message);
  } finally {
    setLoading(submitButton, false);
  }
});

checkHealth();
loadPersons();
loadAttendanceConfig();
loadDashboard();
