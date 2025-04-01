        // Toggle sidebar on mobile
        function toggleSidebar() {
            document.querySelector('.sidebar').classList.toggle('active');
        }

        // Toggle user dropdown
        function toggleDropdown() {
            document.querySelector('.user-dropdown').classList.toggle('active');
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', function(event) {
            const dropdown = document.querySelector('.user-dropdown');
            const profile = document.querySelector('.user-profile');
            
            if (!profile.contains(event.target) && dropdown.classList.contains('active')) {
                dropdown.classList.remove('active');
            }
        });

        // Active menu item based on current page
        document.addEventListener('DOMContentLoaded', function() {
            const currentPath = window.location.pathname;
            const menuItems = document.querySelectorAll('.sidebar-menu a');
            
            menuItems.forEach(item => {
                if (item.getAttribute('href') === currentPath) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });
        });

        document.addEventListener('DOMContentLoaded', function() {
    // Format timestamps as "time ago"
    document.querySelectorAll('.time-ago').forEach(element => {
        const timestamp = new Date(element.dataset.timestamp);
        element.textContent = timeAgo(timestamp);
    });
    
    // You can add code here to calculate percentage changes if needed
});

function timeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    
    const intervals = {
        year: 31536000,
        month: 2592000,
        week: 604800,
        day: 86400,
        hour: 3600,
        minute: 60
    };
    
    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / secondsInUnit);
        if (interval >= 1) {
            return interval + " " + unit + (interval === 1 ? "" : "s") + " ago";
        }
    }
    
    return "just now";
}