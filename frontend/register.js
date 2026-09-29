const API_BASE = 'http://127.0.0.1:5000/api';

const DIRECTIONS = ['center', 'left', 'right', 'up', 'down']

const AUTO_CAPTURE_DELAY = 3000;

let cameraReady = false;
let autoCapture = false;
let activeDirection = null;
let completed = new Set();
let countdownTimer = null;
let countingDown = false;

const stepAccount = document.getElementById('stepAccount')
const usernameInput = document.getElementById('username')
const emailInput = document.getElementById('email')
const accountBtn = document.getElementById('accountBtn')
const accountMsg = document.getElementById('accountMessage')

const stepFace = document.getElementById('stepFace');
const backBtn = document.getElementById('backBtn');
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const camPrompt = document.getElementById('camPrompt');
const camBadge = document.getElementById('camBadge');
const captureBtn = document.getElementById('captureBtn');
const captureBtnText = document.getElementById('captureBtnText');
const faceMsg = document.getElementById('faceMessage');
const activeDirectionName = document.getElementById('activeDirectionName');
const autoToggle = document.getElementById('autoToggle');
const toggleHint = document.getElementById('toggleHint');
const countdownOverlay = document.getElementById('countdownOverlay');
const countdownNum = document.getElementById('countdownNum');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const progressPct = document.getElementById('progressPct');

const stepVerify = document.getElementById('stepVerify');
const videoVerify   = document.getElementById('videoVerify');
const canvasVerify  = document.getElementById('canvasVerify');
const verifyBtn     = document.getElementById('verifyBtn');
const verifyBtnText = document.getElementById('verifyBtnText');
const verifyMsg     = document.getElementById('verifyMessage');

const stepSuccess      = document.getElementById('stepSuccess');
const successUsername  = document.getElementById('successUsername');

let registeredUsername = '';

accountBtn.addEventListener('click', submitAccount);

usernameInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') emailInput.focus()
});

emailInput.addEventListener( 'keydown', e => {
    if (e.key === 'Enter') submitAccount();
})

async function submitAccount() {
    const username = usernameInput.value.trim().toLowerCase();
    const email = emailInput.value.trim().toLowerCase();

    if (!username || !email) {
        setMessage(accountMsg, 'Please fill in both fields.', 'error');
        return;
    }

    if (!email.includes('@')) {
        setMessage(accountMsg, 'Please enter a valid email address.', 'error');
        return;
    }

    setLoading(accountBtn, true, 'Creating account...');
    clearMessage(accountMsg);

    try {
        const response = await fetch (`${API_BASE}/register/init`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json'},
            body: JSON.stringify({username, email}),
        });

        const data = await response.json();

        if (response.ok && data.success) {
            registeredUsername = username;
            showStep(stepFace);
            startCamera();
        } else {
            setMessage(accountMsg, data.error || 'Could not create account. Try again.', 'error');
        }
    } catch (err) {
        setMessage(accountMsg, 'Could not reach the server. Make sure the backend is running.', 'error')
    } finally {
        setLoading(accountBtn, false, 'Continue to face setup');
    }
}

camPrompt.addEventListener('click', startCamera);

async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
        video: {width : {ideal: 640}, height: {ideal : 480}, facingMode: 'user'},
        audio: false,
        });

        video.srcObject = stream;
        videoVerify.srcObject = stream;
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
    document.getElementById(`dir-${dir}`).addEventListener('click',() => {
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
    countingDown = false;
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

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0);
    const image = canvas.toDataURL('image/jpeg', 0.92);

    try {
        const response = await fetch (`${API_BASE}/register/photo`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username: registeredUsername,
                direction,
                image,
            }),
    });

    const data = await response.json();

    if (response.ok && data.success) {
        markDirectionDone(direction);

        if (data.registration_complete) {
            setMessage(faceMsg, 'All 5 photos captured! Proceeding to verification...', 'success');
            setTimeout(() => showStep(stepVerify), 1200);
        } else {
            const remaining = data.directions_remaining;
            setMessage(faceMsg, `Saved. ${remaining.length} direction(s) remaining: ${remaining.join(', ')}.`, 'success');

            if (autoCapture && remaining.length > 0) {
                setTimeout(() => selectDirection(remaining[0]), 800);
            }
        }
    } else {
        setMessage(faceMsg, data.error || 'Could not save photo. Try again.', 'error');
        if (autoCapture) setTimeout(startCountdown, 1500)
    }
    } catch (err) {
        setMessage(faceMsg, 'Could not reach the server', 'error');
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
    const pct = Math.round((count / 5) * 100);

    progressText.textContent = `${count} of 5 completed`;
    progressPct.textContent = `${pct}%`;
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

backBtn.addEventListener('click', () => {
    cancelCountdown();
    showStep(stepAccount);
});

verifyBtn.addEventListener('click', submitVerify);

async function submitVerify() {
    setLoading(verifyBtn, true, 'Verifying...');
    clearMessage(verifyMsg);

    canvasVerify.width = videoVerify.videoWidth;
    canvasVerify.height = videoVerify.videoHeight;
    const ctx = canvasVerify.getContext('2d');
    ctx.translate(canvasVerify.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(videoVerify, 0, 0);
    const image = canvasVerify.toDataURL('image/jpeg', 0.92);

    try {
        const response = await fetch (`${API_BASE}/register/verify`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json' },
            body: JSON.stringify({ username: registeredUsername, image}),
        });

        const data = await response.json();

        if (response.ok && data.success) {
            successUsername.textContent = registeredUsername;
            showStep(stepSuccess);
            stepSuccess.classList.add('show');

            setTimeout(() => {
                window.location.href = 'login.html';
            }, 2500);
        } else {
            setMessage (
                verifyMsg, 
                data.error ||  'Verification failed. Make sure your face is clearly visible.',
        'error'
            );
        }
    } catch (err) {
        setMessage(verifyMsg, 'Could not reach the server.', 'error');
    } finally {
        setLoading(verifyBtn, false, 'Verify and finish');
    }
}

function showStep(stepEl) {
    [stepAccount, stepFace, stepVerify, stepSuccess].forEach(el => {
        el.classList.add('hidden');
    });
    stepEl.classList.remove('hidden');
}

function setLoading(btn, loading, label) {
    btn.disabled = loading;
    btn.classList.toggle('loading', loading);
    const span = btn.querySelector('span') || btn;
    if (span.tagName === 'SPAN') span.textContent = label;
}

function setMessage(el, text, type = 'info') {
    el.textContent = text;
    el.className = `message show ${type}`;
}

function clearMessage(el) {
    el.className = 'message';
}