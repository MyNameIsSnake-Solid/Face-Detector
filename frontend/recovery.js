const API_BASE = 'http://127.0.0.1:5000/api';

const DIRECTIONS = ['center', 'left', 'right', 'up', 'down'];

let cameraReady = false;
let autoCapture = false;
let activeDirection = null;
let completed = new Set();
let countdownTimer = null;
let countingDown = false;
let recoveryToken = '';

const stepRequest = document.getElementById('stepRequest');
const usernameInput = document.getElementById('username');
const requestBtn = document.getElementById('requestBtn');
const requestMsg = document.getElementById('requestMessage');

const stepToken = document.getElementById('stepToken');
const backToRequest = document.getElementById('backToRequest');
const devNote       = document.getElementById('devNote');
const tokenInput    = document.getElementById('tokenInput');
const tokenBtn      = document.getElementById('tokenBtn');
const tokenMsg      = document.getElementById('tokenMessage');
 
const stepFace          = document.getElementById('stepFace');
const video             = document.getElementById('video');
const canvas            = document.getElementById('canvas');
const camPrompt         = document.getElementById('camPrompt');
const camBadge          = document.getElementById('camBadge');
const captureBtn        = document.getElementById('captureBtn');
const faceMsg           = document.getElementById('faceMessage');
const activeDirectionName = document.getElementById('activeDirectionName');
const autoToggle        = document.getElementById('autoToggle');
const toggleHint        = document.getElementById('toggleHint');
const countdownOverlay  = document.getElementById('countdownOverlay');
const countdownNum      = document.getElementById('countdownNum');
const progressFill      = document.getElementById('progressFill');
const progressText      = document.getElementById('progressText');
const progressPct       = document.getElementById('progressPct');
 
const stepSuccess = document.getElementById('stepSuccess');

requestBtn.addEventListener('click', submitRequest);

usernameInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') submitRequest();
});

async function submitRequest() {
    const username = usernameInput.value.trim().toLowerCase();

    if (!username) {
        setMessage(requestMsg, 'Please enter your username.', 'error');
        return;
    }

    setLoading(requestBtn, true, 'Sending...');
    clearMessage(requestMsg);

    try {
    const response = await fetch(`${API_BASE}/recovery/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username }),
    });
 
    const data = await response.json();
    if (response.ok && data.success) {
      showStep(stepToken);
      tokenInput.focus();
    } else {
      setMessage(requestMsg, data.error || 'Something went wrong. Try again.', 'error');
    }
 
  } catch (err) {
    setMessage(requestMsg, 'Could not reach the server. Make sure the backend is running.', 'error');
  } finally {
    setLoading(requestBtn, false, 'Send recovery link');
  }
}

backToRequest.addEventListener('click', () => showStep(stepRequest));

tokenBtn.addEventListener('click', submitToken);

tokenInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') submitToken();
});

function submitToken() {
    const token = tokenInput.value.trim();

    if (!token) {
    setMessage(tokenMsg, 'Please paste your recovery token.', 'error');
    return;
  }

  recoveryToken = token;
  showStep(stepFace);
  startCamera();
}

camPrompt.addEventListener('click', startCamera);

async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
      audio: false,
        });

        video.srcObject = stream;
        camPrompt.style.display = 'none';

        video.onloadedmetadata = () => {
            cameraReady = true;
            camBadge.textContent = 'Camera on';
            camBadge.classList.add('online');
            updateCaptureBtn();
        };
    } catch (err) {
        setMessage(faceMsg, 'Camera access denied. Please allow permissions.', 'error');
    }
}

DIRECTIONS.forEach(dir => {
  document.getElementById(`dir-${dir}`).addEventListener('click', () => {
    if (completed.has(dir)) return;
    selectDirection(dir);
  });
});

function selectDirection(dir) {
    if (activeDirection) {
      const prev = document.getElementById(`dir-${activeDirection}`);
      prev.classList.remove('active');
      setBadge(activeDirection, 'pending');
    }

    activeDirection = dir;

    const el = document.getElementById(`dir-${dir}`);
    el.classList.add('active');
    setBadge(dir, 'active');

    activeDirectionName.textContent = dir.charAt(0).toUpperCase() + dir.slice(1);
    clearMessage(faceMsg);
    updateCaptureBtn();

    if (autoCapture && cameraReady) {
      startCountdown();
    }
}

autoToggle.addEventListener('click', () => {
  autoCapture = !autoCapture;
  autoToggle.classList.toggle('on', autoCapture);
  toggleHint.textContent = autoCapture ? 'On' : 'Off';
  captureBtn.style.display = autoCapture ? 'none' : 'block';

  if (autoCapture && activeDirection && cameraReady) {
    startCountdown();
  } else {
    cancelCountdown();
  }
});

function startCountdown() {
  if (countingDown) return;
  countingDown = true;
 
  let count = 3;
  countdownNum.textContent = count;
  countdownOverlay.classList.remove('hidden');
 
  countdownTimer = setInterval(() => {
    count--;
    countdownNum.textContent = count;
 
    if (count <= 0) {
      cancelCountdown();
      capturePhoto();
    }
  }, 1000);
}

function cancelCountdown() {
  clearInterval(countdownTimer);
  countdownTimer = null;
  countingDown   = false;
  countdownOverlay.classList.add('hidden');
}

captureBtn.addEventListener('click', () => {
  if (!activeDirection || !cameraReady) return;
  capturePhoto();
});

async function capturePhoto() {
  if (!activeDirection || !cameraReady) return;
 
  const direction = activeDirection;
 
  setLoading(captureBtn, true, 'Sending...');
  clearMessage(faceMsg);
 
  canvas.width  = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.translate(canvas.width, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(video, 0, 0);
  const image = canvas.toDataURL('image/jpeg', 0.92);
 
  try {
    const response = await fetch(`${API_BASE}/recovery/re-register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        token: recoveryToken,
        direction,
        image,
      }),
    });
 
    const data = await response.json();
 
    if (response.ok && data.success) {
      markDirectionDone(direction);
 
      if (data.registration_complete) {
        setMessage(faceMsg, 'All 5 photos captured! Your face data has been updated.', 'success');
        setTimeout(() => {
          showStep(stepSuccess);
          stepSuccess.classList.add('show');
          setTimeout(() => { window.location.href = 'login.html'; }, 2500);
        }, 1000);
      } else {
        const remaining = data.directions_remaining;
        setMessage(faceMsg, `Saved. ${remaining.length} direction(s) remaining: ${remaining.join(', ')}.`, 'success');
 
        if (autoCapture && remaining.length > 0) {
          setTimeout(() => selectDirection(remaining[0]), 800);
        }
      }
    } else {
      setMessage(faceMsg, data.error || 'Could not save photo. Try again.', 'error');
      if (autoCapture) setTimeout(startCountdown, 1500);
    }
 
  } catch (err) {
    setMessage(faceMsg, 'Could not reach the server.', 'error');
  } finally {
    setLoading(captureBtn, false, 'Capture photo');
  }
}
 
function markDirectionDone(dir) {
  completed.add(dir);
 
  const el = document.getElementById(`dir-${dir}`);
  el.classList.remove('active');
  el.classList.add('done');
  setBadge(dir, 'done');
 
  if (activeDirection === dir) {
    activeDirection = null;
    activeDirectionName.textContent = 'None selected';
  }
 
  updateProgress();
  updateCaptureBtn();
}

function updateProgress() {
  const count = completed.size;
  const pct   = Math.round((count / 5) * 100);
 
  progressText.textContent = `${count} of 5 completed`;
  progressPct.textContent  = `${pct}%`;
  progressFill.style.width = `${pct}%`;
}
 
function updateCaptureBtn() {
  captureBtn.disabled = !cameraReady || !activeDirection || autoCapture;
}
 
function setBadge(dir, state) {
  const badge = document.querySelector(`#dir-${dir} .dir-badge`);
  if (!badge) return;
  badge.className = `dir-badge ${state}`;
  badge.textContent = state.charAt(0).toUpperCase() + state.slice(1);
}

function showStep(stepEl) {
  [stepRequest, stepToken, stepFace, stepSuccess].forEach(el => {
    el.classList.add('hidden');
  });
  stepEl.classList.remove('hidden');
}
 
function setLoading(btn, loading, label) {
  btn.disabled = loading;
  btn.classList.toggle('loading', loading);
  const span = btn.querySelector('span');
  if (span) span.textContent = label;
}
 
function setMessage(el, text, type = 'info') {
  el.textContent = text;
  el.className = `message show ${type}`;
}
 
function clearMessage(el) {
  el.className = 'message';
}