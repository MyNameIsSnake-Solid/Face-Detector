const API_BASE = 'http://127.0.0.1:5000/api';

let cameraReady = false;

const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const camPrompt = document.getElementById('camPrompt');
const camBadge = document.getElementById('camBadge');
const loginBtn = document.getElementById('loginBtn');
const loginBtnText = document.getElementById('loginBtnText');
const messageEl = document.getElementById('message');
const confWrap = document.getElementById('confidenceWrap');
const confFill = document.getElementById('confidenceFill');
const confVal = document.getElementById('confidenceVal');
const loginCard = document.getElementById('loginCard');
const successCard = document.getElementById('successCard');
const successUser = document.getElementById('successUser');

async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {width: {ideal: 640}, height: {ideal: 480}, facingMode: 'user'},
            audio: false,
        });

        video.srcObject = stream;
        camPrompt.style.display = 'none';

        video.onloadedmetadata= () => {
            cameraReady = true;
            camBadge.textContent = 'Camera on';
            camBadge.classList.add('online');
            loginBtn.disabled = false;
        };
    } catch (err) {
        setMessage('Camera access denied. Please allow camera permissions and try again.', 'error');
    }
}

function captureFrame() {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext('2d');

    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0);

    return canvas.toDataURL('image/jpeg', 0.92);
}

async function attemptLogin() {
    const username = document.getElementById('username').value.trim().toLowerCase();

    if (!username) {
        setMessage('Please enter your username.', 'error');
        return;
    }

    if (!cameraReady) {
        setMessage('Please start the camera first.', 'error');
        return;
    }
    
    setLoading(true);
    clearMessage();
    hideConfidence();

    const image = captureFrame();

    try {
        const response = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username , image})
        });

        const data = await response.json();

        if (response.ok && data.success) {
            handleSuccess(data);
        } else {
            handleFailure(response.status, data);
        }
    } catch (err) {
        setMessage('Could not reach the server. Make sure the backend is running.', 'error');
    } finally {
        setLoading(false);
    }

}

function handleSuccess(data){
    sessionStorage.setItem('auth_token', data.token);

    sessionStorage.setItem('username', data.username);

    showConfidence(data.confidence);

    setTimeout(() => {
        loginCard.style.display = 'none';
        successUser.textContent = data.username;
        successCard.classList.add('show');

        setTimeout(() => {
            window.location.href = 'dashboard.html';
        }, 2000);
    
    }, 500);
}

    function handleFailure(status, data) {
        if (status === 429) {
            setMessage('Account locked after too many failed attempts. Use the recovery option below.', 'error');
            loginBtn.disabled = true;
            return;
        }

        if (data.confidence !== undefined) {
            showConfidence(data.confidence);
        }

        if (status === 401) {
            setMessage('Face not recognised. Try again with better lighting or a more direct angle.', 'error');
        } else if (status === 400) {
            setMessage(data.error || 'Something went wrong. Please try again.', 'error');
        } else {
            setMessage('Login failed. Please try again.', 'error');
        }
    }

    function setLoading(loading) {
        loginBtn.disabled = loading;
        loginBtn.classList.toggle('loading', loading);
        loginBtnText.textContent = loading ? 'Scanning...' : 'Scan face to log in';
    }

    function setMessage(text, type = 'info') {
        messageEl.textContent = text;
        messageEl.className = `message show ${type}`;
    }

    function clearMessage() {
        messageEl.className = 'message';
    }

    function showConfidence(confidence) {
        const pct = Math.round(confidence * 100);
        confWrap.classList.add('show');
        confVal.textContent = `${pct}%`;

        setTimeout(() => {
            confFill.style.width = `${pct}%`;
            confFill.style.background = pct >= 60
            ? 'var(--green)'
            : 'var(--red)';

        }, 50)
    }

    function hideConfidence () {
        confWrap.classList.remove('show');
        confFill.style.width = '0%';
    }

    camPrompt.addEventListener('click', startCamera);
    loginBtn.addEventListener('click', attemptLogin);

    document.getElementById('username').addEventListener
    ('keydown', e => {
        if (e.key === 'Enter' && cameraReady) attemptLogin();
        }
    );

    navigator.permissions?.query({ name: 'camera'}).then(result =>
    { 
        if (result.state === 'granted') startCamera();
    }
    )