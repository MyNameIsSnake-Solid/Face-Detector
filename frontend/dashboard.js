const token = sessionStorage.getItem('auth_token');
const username = sessionStorage.getItem('username');

if (!token || !username) {
    window.location.href = 'login.html';
}

function parseJWTPayload(jwt) {
    try {
        const base64 = jwt.split('.')[1];

        return JSON.parse(atob(base64));
    } catch (e) {
        return null;
    }
}

function formatExpiry(unixTimestamp) {
    const date = new Date(unixTimestamp * 1000);
    return date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
}

const payload = parseJWTPayload(token);

document.getElementById('navUsername').textContent = username;

document.getElementById('welcomeTitle').textContent = `Welcome back, ${username}`;

document.getElementById('statUsername').textContent = username;
document.getElementById('statExpiry').textContent = payload ? formatExpiry(payload.exp) : 'Unknown';

document.getElementById('tokenText').textContent = token;

const copyBtn = document.getElementById('copyBtn');

copyBtn.addEventListener('click', async () => {
    try {
        await navigator.clipboard.writeText(token);
        copyBtn.textContent = 'Copied!';
        copyBtn.classList.add('copied');

        setTimeout(() => {
            copyBtn.textContent = 'Copy';
            copyBtn.classList.remove('copied');
        }, 2000);
    } catch (err) {
        copyBtn.textContent = 'Failed';
        setTimeout(() => {copyBtn.textContent = 'Copy'; }, 2000);
    }
});

document.getElementById('logoutBtn').addEventListener('click', () => {
    sessionStorage.removeItem('auth_token');
    sessionStorage.removeItem('username');
    window.location.href = 'login.html';
});

if (payload && payload.exp) {
    const nowSeconds = Math.floor(Date.now() / 1000);

    if (nowSeconds > payload.exp) {
        sessionStorage.removeItem('auth_token');
        sessionStorage.removeItem('username');
        window.location.href = 'login.html';
    }

    const msUntilExpiry = (payload.exp - nowSeconds) * 1000;
setTimeout(() => {
    sessionStorage.removeItem('auth_token');
    sessionStorage.removeItem('username');
    window.location.href = 'login.html';
}, msUntilExpiry);

}

