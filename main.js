// Tab switching
function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    const content = document.getElementById(tabId);
    if (content) content.classList.add('active');
    event.currentTarget.classList.add('active');
}

// Auto-dismiss alerts after 4s
document.querySelectorAll('.alert').forEach(a => {
    setTimeout(() => { if (a.parentElement) a.remove(); }, 4000);
});

// Notification badge
async function updateNotifCount() {
    try {
        const res = await fetch('/notifications_count');
        const data = await res.json();
        const badge = document.getElementById('notif-count');
        if (badge) {
            if (data.count > 0) {
                badge.textContent = data.count;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }
    } catch (e) {}
}

updateNotifCount();
setInterval(updateNotifCount, 30000);
