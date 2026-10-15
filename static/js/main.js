// Modern Interactive Enhancements
document.addEventListener('DOMContentLoaded', function () {
  // Mobile sidebar toggle
  const toggleBtn = document.getElementById('sidebarToggleBtn');
  const sidebar = document.getElementById('appSidebar');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', function () {
      sidebar.classList.toggle('open');
    });

    // Close on click outside
    document.addEventListener('click', function (e) {
      if (
        sidebar.classList.contains('open') &&
        !sidebar.contains(e.target) &&
        !toggleBtn.contains(e.target)
      ) {
        sidebar.classList.remove('open');
      }
    });
  }

  // Live Digital Clock
  const clockEl = document.getElementById('liveClockDisplay');
  if (clockEl) {
    function updateClock() {
      const now = new Date();
      const options = {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
      };
      clockEl.textContent = now.toLocaleDateString('en-US', options);
    }
    updateClock();
    setInterval(updateClock, 1000);
  }

  // Dismissible Alerts
  document.querySelectorAll('.alert-close').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const alert = this.closest('.alert');
      if (alert) {
        alert.style.opacity = '0';
        setTimeout(() => alert.remove(), 200);
      }
    });
  });
});
