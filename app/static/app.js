const state = {
  petFile: null,
  cameraStream: null,
  attendanceConfig: null,
  lastPosition: null,
};

const FRAME_COUNT = 4;
const FRAME_INTERVAL_MS = 220;

const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");
const healthStatus = document.getElementById("healthStatus");

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((item) => item.classList.remove("active"));
    panels.forEach((panel) => panel.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(`${tab.dataset.tab}-panel`).classList.add("active");
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

function renderPetResult(data) {
  document.getElementById("petResultEmpty").classList.add("hidden");
  const content = document.getElementById("petResultContent");
  content.classList.remove("hidden");

  const badge = document.getElementById("petBadge");
  badge.textContent = data.label.toUpperCase();
  badge.className = `badge ${data.label}`;

  document.getElementById("petMessage").textContent = data.message;
  document.getElementById("petConfidence").textContent = `Confidence: ${data.confidence}%`;

  const list = document.getElementById("petPredictions");
  list.innerHTML = "";
  (data.top_predictions || []).forEach((item) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${item.label}</span><strong>${item.confidence}%</strong>`;
    list.appendChild(li);
  });
}

const petInput = document.getElementById("petInput");
const petPreview = document.getElementById("petPreview");
const petPreviewWrap = document.getElementById("petPreviewWrap");
const petClassifyBtn = document.getElementById("petClassifyBtn");

petInput.addEventListener("change", () => {
  const file = petInput.files?.[0];
  state.petFile = file || null;
  petClassifyBtn.disabled = !state.petFile;

  if (!file) {
    petPreviewWrap.classList.add("hidden");
    return;
  }

  petPreview.src = URL.createObjectURL(file);
  petPreviewWrap.classList.remove("hidden");
});

petClassifyBtn.addEventListener("click", async () => {
  if (!state.petFile) return;

  const formData = new FormData();
  formData.append("file", state.petFile);

  setLoading(petClassifyBtn, true);
  try {
    const response = await fetch("/api/classify/pet", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Classification failed");
    renderPetResult(data);
  } catch (error) {
    alert(error.message);
  } finally {
    setLoading(petClassifyBtn, false);
  }
});

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
    document.getElementById("personPhoto").src = `${data.person.photo_url}?t=${Date.now()}`;
  }

  document.getElementById("faceMessage").textContent = data.message;
  const details = [];
  if (data.office_name && data.distance_meters !== null && data.distance_meters !== undefined) {
    details.push(`Distance from ${data.office_name}: ${Math.round(data.distance_meters)}m`);
  }
  if (data.confidence) {
    details.push(`Match confidence: ${data.confidence}%`);
  }
  document.getElementById("faceConfidence").textContent = details.join(" • ");
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

  const response = await fetch("/api/recognize/face", {
    method: "POST",
    body: formData,
  });
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
      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 0,
      },
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
  if (state.attendanceConfig && !state.attendanceConfig.enabled) {
    return null;
  }

  setLocationStatus("warning", "Checking your office location...");
  const position = await getCurrentPosition();
  state.lastPosition = position;

  const { latitude, longitude, accuracy } = position.coords;
  if (state.attendanceConfig && accuracy > state.attendanceConfig.max_accuracy_meters) {
    throw new Error(
      `Location accuracy is too low (${Math.round(accuracy)}m). Move near a window or enable precise location at the office.`,
    );
  }

  setLocationStatus("ready", `Location captured with ${Math.round(accuracy)}m accuracy.`);
  return position;
}

startCameraBtn.addEventListener("click", async () => {
  try {
    if (state.cameraStream) {
      state.cameraStream.getTracks().forEach((track) => track.stop());
    }
    state.cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user" },
      audio: false,
    });
    cameraVideo.srcObject = state.cameraStream;
    captureFaceBtn.disabled = false;
    captureHint.textContent = "Camera ready. Click Verify Attendance to run live face checks.";
  } catch (error) {
    alert("Unable to access camera. Please allow camera permission.");
  }
});

captureFaceBtn.addEventListener("click", async () => {
  const width = cameraVideo.videoWidth;
  const height = cameraVideo.videoHeight;
  if (!width || !height) {
    alert("Camera is not ready yet.");
    return;
  }

  cameraCanvas.width = width;
  cameraCanvas.height = height;
  const context = cameraCanvas.getContext("2d");

  setLoading(captureFaceBtn, true, "Checking location...");
  captureHint.textContent = "Verifying office location before attendance check-in...";

  try {
    const position = await verifyOfficeLocation();

    setLoading(captureFaceBtn, true, "Verifying live face...");
    captureHint.textContent = "Capturing live frames for anti-spoof verification...";

    const blobs = [];
    for (let index = 0; index < FRAME_COUNT; index += 1) {
      context.drawImage(cameraVideo, 0, 0, width, height);
      const blob = await new Promise((resolve) => cameraCanvas.toBlob(resolve, "image/jpeg", 0.92));
      blobs.push(blob);
      if (index < FRAME_COUNT - 1) {
        await sleep(FRAME_INTERVAL_MS);
      }
    }
    await recognizeFaceFrames(blobs, position);
    captureHint.textContent = "Verification complete.";
  } catch (error) {
    setLocationStatus("error", error.message);
    renderFaceResult({
      restricted: true,
      recognized: false,
      message: error.message,
    });
    captureHint.textContent = "Verification failed. Attendance requires office presence and live face verification.";
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
  } catch (error) {
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
    const response = await fetch("/api/persons/register", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Registration failed");

    registerForm.reset();
    registerPhotoLabel.textContent = "Upload a clear front-facing photo";
    await loadPersons();
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
