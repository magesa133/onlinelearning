// Dashboard-specific JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Export button
    const exportBtn = document.getElementById('exportData');
    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            // TODO: Implement export functionality
            console.log('Exporting data...');
            alert('Export functionality will be implemented soon!');
        });
    }
    
    // Quick action modal
    const quickActionModal = document.getElementById('quickActionModal');
    if (quickActionModal) {
        // Initialize modal if using Bootstrap
        // const modal = new bootstrap.Modal(quickActionModal);
        
        // Or custom implementation
        const modalOpenBtns = document.querySelectorAll('[data-bs-target="#quickActionModal"]');
        modalOpenBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                quickActionModal.classList.add('active');
            });
        });
        
        const modalCloseBtns = quickActionModal.querySelectorAll('.btn-close, [data-dismiss="modal"]');
        modalCloseBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                quickActionModal.classList.remove('active');
            });
        });
    }
    
    // Confirmation modal
    const confirmModal = document.getElementById('confirmModal');
    if (confirmModal) {
        // Store the callback function
        let confirmCallback = null;
        
        // Set up modal triggers
        document.querySelectorAll('[data-confirm]').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                const message = this.getAttribute('data-confirm') || 'Are you sure you want to perform this action?';
                confirmModal.querySelector('#confirmMessage').textContent = message;
                confirmModal.classList.add('active');
                
                // Store the callback
                confirmCallback = () => {
                    window.location.href = this.href;
                };
            });
        });
        
        // Confirm button
        confirmModal.querySelector('#confirmAction').addEventListener('click', function() {
            if (confirmCallback) {
                confirmCallback();
            }
            confirmModal.classList.remove('active');
        });
        
        // Cancel button
        confirmModal.querySelector('.btn-secondary').addEventListener('click', function() {
            confirmModal.classList.remove('active');
            confirmCallback = null;
        });
    }
    
    // Initialize charts (example with Chart.js)
    const chartContainers = document.querySelectorAll('.chart-container');
    if (chartContainers.length > 0 && typeof Chart !== 'undefined') {
        chartContainers.forEach(container => {
            const ctx = container.querySelector('canvas').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                    datasets: [{
                        label: 'New Students',
                        data: [12, 19, 3, 5, 2, 3],
                        backgroundColor: 'rgba(76, 175, 80, 0.2)',
                        borderColor: 'rgba(76, 175, 80, 1)',
                        borderWidth: 2,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        });
    }
});