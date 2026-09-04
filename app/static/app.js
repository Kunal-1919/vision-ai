const TOKEN_KEY = "visionai_token";

const TAB_CONFIG = [
  { id: "dashboard", label: "Dashboard", roles: ["admin"] },
  { id: "biometric", label: "Biometric Hardware", roles: ["admin"] },
  { id: "face", label: "Attendance Check-in", roles: ["employee"] },
  { id: "register", label: "Enroll Employee", roles: ["admin"] },
];

const state = {
  token: localStorage.getItem(TOKEN_KEY),
  user: null,
  cameraStream: null,
  attendanceConfig: null,
};

const FRAME_COUNT = 4;
const FRAME_INTERVAL_MS = 220;

const REASON_LABELS = {
  geofence: "Outside office",
  scene: "Phone / device detected",
  liveness: "Spoof detected",
  face_mismatch: "Face not recognized",
  identity_mismatch: "Wrong account",
  verified: "Verified",
};

const loginScreen = document.getElementById("loginScreen");
const appShell = document.getElementById("appShell");
const loginForm = document.getElementById("loginForm");
const loginError = document.getElementById("loginError");
const logoutBtn = document.getElementById("logoutBtn");
const mainTabs = document.getElementById("mainTabs");
const healthStatus = document.getElementById("healthStatus");

async function parseJsonResponse(response) {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(
      text.startsWith("Internal")
        ? "Server error. Please restart the app and try again."
        : text || "Unexpected server response",
    );
  }
}

async function apiFetchJson(url, options = {}) {
  const response = await apiFetch(url, options);
  const data = await parseJsonResponse(response);
  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return data;
}

async function apiFetch(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    logout();
    throw new Error("Session expired. Please sign in again.");
  }
  return response;
}

function showLogin() {
  loginScreen.classList.remove("hidden");
  appShell.classList.add("hidden");
}

function showApp() {
  loginScreen.classList.add("hidden");
  appShell.classList.remove("hidden");
}

function logout() {
  state.token = null;
  state.user = null;
  localStorage.removeItem(TOKEN_KEY);
  if (state.cameraStream) {
    state.cameraStream.getTracks().forEach((track) => track.stop());
    state.cameraStream = null;
  }
  showLogin();
}

function buildTabs() {
  mainTabs.innerHTML = "";
  const allowed = TAB_CONFIG.filter((tab) => tab.roles.includes(state.user.role));
  allowed.forEach((tab, index) => {
    const button = document.createElement("button");
    button.className = `tab${index === 0 ? " active" : ""}`;
    button.dataset.tab = tab.id;
    button.textContent = tab.label;
    button.addEventListener("click", () => activateTab(tab.id));
    mainTabs.appendChild(button);
  });

  document.querySelectorAll(".panel").forEach((panel) => panel.classList.remove("active"));
  if (allowed.length) {
    document.getElementById(`${allowed[0].id}-panel`).classList.add("active");
  }
}

function activateTab(tabId) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === tabId);
  });
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `${tabId}-panel`);
  });
  if (tabId === "dashboard") loadDashboard();
  if (tabId === "biometric") loadBiometricDevices();
  if (tabId === "register") loadPersons();
}

function updateUserHeader() {
  document.getElementById("userName").textContent = state.user.name;
  const roleChip = document.getElementById("userRole");
  roleChip.textContent = state.user.role;
  roleChip.className = `role-chip ${state.user.role}`;

  const hint = document.getElementById("employeeCheckinHint");
  if (hint && state.user.role === "employee") {
    hint.textContent = `Signed in as ${state.user.name}. Only your enrolled face can mark attendance.`;
  }
}

async function initSession() {
  if (!state.token) {
    showLogin();
    return;
  }
  try {
    const data = await apiFetchJson("/api/auth/me");
    state.user = data.user;
    showApp();
    buildTabs();
    updateUserHeader();
    await Promise.all([checkHealth(), loadAttendanceConfig()]);
    if (state.user.role === "admin") {
      await Promise.all([loadDashboard(), loadPersons()]);
    }
  } catch {
    logout();
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.classList.add("hidden");
  const formData = new FormData(loginForm);
  const payload = {
    username: formData.get("username"),
    password: formData.get("password"),
  };

  const submitBtn = loginForm.querySelector("button[type='submit']");
  setLoading(submitBtn, true, "Signing in...");
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await parseJsonResponse(response);
    if (!response.ok) throw new Error(data.detail || "Login failed");
    state.token = data.access_token;
    state.user = data.user;
    localStorage.setItem(TOKEN_KEY, state.token);
    loginForm.reset();
    showApp();
    buildTabs();
    updateUserHeader();
    await Promise.all([checkHealth(), loadAttendanceConfig()]);
    if (state.user.role === "admin") {
      await Promise.all([loadDashboard(), loadPersons()]);
    }
  } catch (error) {
    loginError.textContent = error.message;
    loginError.classList.remove("hidden");
  } finally {
    setLoading(submitBtn, false);
  }
});

logoutBtn.addEventListener("click", logout);

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("Service unavailable");
    healthStatus.textContent = "Service online";
    healthStatus.classList.add("ok");
  } catch {
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
  return new Date(isoString).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

async function loadDashboard() {
  if (state.user?.role !== "admin") return;
  try {
    const [stats, logs] = await Promise.all([
      apiFetchJson("/api/attendance/stats"),
      apiFetchJson("/api/attendance/logs?limit=15"),
    ]);

    document.getElementById("statEnrolled").textContent = stats.enrolled_count ?? 0;
    document.getElementById("statCheckins").textContent = stats.check_ins_today ?? 0;
    document.getElementById("statBlocked").textContent = stats.blocked_today ?? 0;
    document.getElementById("statTotal").textContent = stats.total_check_ins ?? 0;

    const reasonsEl = document.getElementById("blockedReasons");
    const reasons = stats.blocked_reasons_today || {};
    const reasonKeys = Object.keys(reasons);
    reasonsEl.innerHTML = reasonKeys.length
      ? reasonKeys.map((key) => `
        <div class="reason-item">
          <span>${REASON_LABELS[key] || key}</span>
          <strong>${reasons[key]}</strong>
        </div>`).join("")
      : '<p class="muted">No blocked attempts today.</p>';

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
    const photoUrl = state.token
      ? `${data.person.photo_url}?token=${encodeURIComponent(state.token)}&t=${Date.now()}`
      : `${data.person.photo_url}?t=${Date.now()}`;
    document.getElementById("personPhoto").src = photoUrl;
  }

  document.getElementById("faceMessage").textContent = data.message;
  const details = [];
  if (data.office_name && data.distance_meters != null) {
    details.push(`Distance from ${data.office_name}: ${Math.round(data.distance_meters)}m`);
  }
  if (data.confidence) details.push(`Match confidence: ${data.confidence}%`);
  document.getElementById("faceConfidence").textContent = details.join(" • ");
}

async function recognizeFaceFrames(blobs, position) {
  const formData = new FormData();
  blobs.forEach((blob, index) => formData.append("files", blob, `frame-${index}.jpg`));
  if (position) {
    formData.append("latitude", String(position.coords.latitude));
    formData.append("longitude", String(position.coords.longitude));
    formData.append("accuracy_meters", String(position.coords.accuracy));
  }
  const data = await apiFetchJson("/api/recognize/face", { method: "POST", body: formData });
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
  if (!state.token) return;
  try {
    state.attendanceConfig = await apiFetchJson("/api/attendance/config");
    const chip = document.getElementById("adminGeofenceStatusChip");
    if (chip) {
      chip.textContent = state.attendanceConfig.enabled ? "Geofence Active" : "Geofence Disabled";
      chip.className = `status-chip ${state.attendanceConfig.enabled ? "success" : "blocked"}`;
    }
    const nameEl = document.getElementById("geoAdminName");
    if (nameEl) {
      nameEl.value = state.attendanceConfig.office_name || "";
      document.getElementById("geoAdminEnabled").value = String(state.attendanceConfig.enabled);
      document.getElementById("geoAdminLat").value = state.attendanceConfig.latitude ?? "";
      document.getElementById("geoAdminLon").value = state.attendanceConfig.longitude ?? "";
      document.getElementById("geoAdminRadius").value = state.attendanceConfig.radius_meters ?? "";
      document.getElementById("geoAdminMaxAcc").value = state.attendanceConfig.max_accuracy_meters ?? "";
    }

    if (!state.attendanceConfig.enabled) {
      setLocationStatus("warning", "Office geofence is currently disabled (testing mode).");
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
  if (state.user?.role !== "admin") return;
  const container = document.getElementById("personList");
  try {
    const data = await apiFetchJson("/api/persons");
    container.innerHTML = "";
    if (!data.persons.length) {
      container.innerHTML = '<p class="muted">No employees enrolled yet.</p>';
      return;
    }
    const template = document.getElementById("personListItemTemplate");
    data.persons.forEach((person) => {
      const node = template.content.cloneNode(true);
      const photoUrl = state.token
        ? `${person.photo_url}?token=${encodeURIComponent(state.token)}&t=${Date.now()}`
        : `${person.photo_url}?t=${Date.now()}`;
      node.querySelector("img").src = photoUrl;
      node.querySelector("h3").textContent = person.name;
      node.querySelector(".role").textContent = person.role || "Role not set";
      node.querySelector(".department").textContent = person.department || "";

      const deleteBtn = node.querySelector(".delete-btn");
      if (deleteBtn) {
        deleteBtn.addEventListener("click", async () => {
          if (confirm(`Are you sure you want to delete employee '${person.name}'?`)) {
            try {
              await apiFetchJson(`/api/persons/${person.id}`, { method: "DELETE" });
              await loadPersons();
              await loadDashboard();
            } catch (err) {
              alert(err.message);
            }
          }
        });
      }

      container.appendChild(node);
    });
  } catch {
    container.innerHTML = '<p class="muted">Unable to load enrolled employees.</p>';
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
  setLoading(submitButton, true, "Enrolling...");
  try {
    const data = await apiFetchJson("/api/persons/register", { method: "POST", body: formData });
    registerForm.reset();
    registerPhotoLabel.textContent = "Upload a clear front-facing photo";
    await loadPersons();
    await loadDashboard();
    alert(`Enrolled ${data.person.name}. Employee login: ${data.user.username}`);
  } catch (error) {
    alert(error.message);
  } finally {
    setLoading(submitButton, false);
  }
});

async function loadBiometricDevices() {
  if (state.user?.role !== "admin") return;
  const container = document.getElementById("biometricDeviceList");
  try {
    const data = await apiFetchJson("/api/biometric/devices");
    container.innerHTML = "";
    if (!data.devices?.length) {
      container.innerHTML = '<p class="muted">No biometric terminals linked yet.</p>';
      return;
    }
    data.devices.forEach((device) => {
      const card = document.createElement("article");
      card.className = "biometric-card";
      card.innerHTML = `
        <div class="biometric-header">
          <div>
            <h3>${device.name}</h3>
            <span class="vendor-chip">${device.vendor} · ${device.device_type}</span>
          </div>
          <span class="status-chip ${device.status}">${device.status}</span>
        </div>
        <div class="biometric-details">
          <p><strong>S/N:</strong> <code>${device.serial_number}</code></p>
          <p><strong>IP Address:</strong> <code>${device.ip_address}</code></p>
          <p><strong>Location:</strong> ${device.location}</p>
          <p><strong>Firmware:</strong> ${device.firmware_version}</p>
        </div>
        <button class="delete-btn unlink-device-btn" type="button" data-id="${device.id}">Unlink Terminal</button>
      `;
      const unlinkBtn = card.querySelector(".unlink-device-btn");
      unlinkBtn.addEventListener("click", async () => {
        if (confirm(`Unlink biometric terminal '${device.name}'?`)) {
          try {
            await apiFetchJson(`/api/biometric/devices/${device.id}`, { method: "DELETE" });
            await loadBiometricDevices();
          } catch (err) {
            alert(err.message);
          }
        }
      });
      container.appendChild(card);
    });
  } catch (error) {
    container.innerHTML = `<p class="muted">Unable to load biometric terminals: ${error.message}</p>`;
  }
}

const biometricDeviceForm = document.getElementById("biometricDeviceForm");
if (biometricDeviceForm) {
  biometricDeviceForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitBtn = biometricDeviceForm.querySelector("button[type='submit']");
    setLoading(submitBtn, true, "Linking...");
    const formData = new FormData(biometricDeviceForm);
    const payload = {
      name: formData.get("name"),
      serial_number: formData.get("serial_number"),
      ip_address: formData.get("ip_address"),
      device_type: formData.get("device_type"),
      vendor: formData.get("vendor"),
      location: formData.get("location"),
    };
    try {
      await apiFetchJson("/api/biometric/devices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      biometricDeviceForm.reset();
      await loadBiometricDevices();
      alert(`Linked biometric terminal '${payload.name}' successfully.`);
    } catch (error) {
      alert(error.message);
    } finally {
      setLoading(submitBtn, false);
    }
  });
}

const useCurrentGpsBtn = document.getElementById("useCurrentGpsBtn");
if (useCurrentGpsBtn) {
  useCurrentGpsBtn.addEventListener("click", async () => {
    setLoading(useCurrentGpsBtn, true, "Acquiring GPS...");
    try {
      const pos = await getCurrentPosition();
      document.getElementById("geoAdminLat").value = pos.coords.latitude.toFixed(7);
      document.getElementById("geoAdminLon").value = pos.coords.longitude.toFixed(7);
      alert(`Acquired GPS position: Lat ${pos.coords.latitude.toFixed(6)}, Lon ${pos.coords.longitude.toFixed(6)} (Accuracy ${Math.round(pos.coords.accuracy)}m). Click "Save Geofence Configuration" to save.`);
    } catch (err) {
      alert(`GPS Error: ${err.message}`);
    } finally {
      setLoading(useCurrentGpsBtn, false);
    }
  });
}

const adminGeofenceForm = document.getElementById("adminGeofenceForm");
if (adminGeofenceForm) {
  adminGeofenceForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitBtn = adminGeofenceForm.querySelector("button[type='submit']");
    setLoading(submitBtn, true, "Saving...");
    const payload = {
      name: document.getElementById("geoAdminName").value,
      enabled: document.getElementById("geoAdminEnabled").value === "true",
      latitude: parseFloat(document.getElementById("geoAdminLat").value),
      longitude: parseFloat(document.getElementById("geoAdminLon").value),
      radius_meters: parseFloat(document.getElementById("geoAdminRadius").value),
      max_accuracy_meters: parseFloat(document.getElementById("geoAdminMaxAcc").value),
    };
    try {
      await apiFetchJson("/api/attendance/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      await loadAttendanceConfig();
      alert(`Geofence settings updated successfully for '${payload.name}'.`);
    } catch (err) {
      alert(`Failed to update geofence: ${err.message}`);
    } finally {
      setLoading(submitBtn, false);
    }
  });
}

initSession();
