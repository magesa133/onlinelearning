function logout() {
    window.location.href = "{{ url_for('logout') }}";
}

function toggleDropdown() {
    const dropdown = document.getElementById('dropdown-menu');
    dropdown.classList.toggle('show'); 
}

// Close the dropdown menu if the user clicks outside of it
window.addEventListener('click', (event) => {
    if (!event.target.matches('.user-icon') && 
        !event.target.matches('.dropdown-menu')) {
        const dropdowns = document.querySelectorAll('.dropdown-menu');
        dropdowns.forEach(dropdown => {
            dropdown.classList.remove('show');
        });
    }
});