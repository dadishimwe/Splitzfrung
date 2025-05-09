// ZUBA Inventory System - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Search functionality
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('keyup', function(e) {
            if (e.key === 'Enter') {
                const searchForm = document.getElementById('searchForm');
                if (searchForm) {
                    searchForm.submit();
                }
            }
        });
    }

    // Filter form auto-submit
    const filterForm = document.getElementById('filterForm');
    if (filterForm) {
        const filterSelects = filterForm.querySelectorAll('select');
        filterSelects.forEach(select => {
            select.addEventListener('change', function() {
                filterForm.submit();
            });
        });
    }

    // Confirmation dialogs
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const message = this.getAttribute('data-confirm');
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });

    // Serial number validation
    const serialNumberInput = document.getElementById('serialNumber');
    if (serialNumberInput) {
        serialNumberInput.addEventListener('blur', function() {
            const serialNumber = this.value.trim();
            if (serialNumber) {
                validateSerialNumber(serialNumber);
            }
        });
    }

    // Status color indicators
    const statusElements = document.querySelectorAll('.item-status');
    statusElements.forEach(element => {
        const status = element.textContent.trim();
        if (status === 'In stock') {
            element.classList.add('status-in-stock');
        } else if (status === 'Installed') {
            element.classList.add('status-installed');
        } else if (status === 'Maintenance') {
            element.classList.add('status-maintenance');
        } else if (status === 'Decommissioned') {
            element.classList.add('status-decommissioned');
        }
    });

    // Date picker initialization for all date inputs
    const dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(input => {
        if (!input.value) {
            // Set default value to today for empty date fields if needed
            // Uncomment the line below if you want this behavior
            // input.valueAsDate = new Date();
        }
    });

    // Dashboard charts
    initDashboardCharts();
});

// Function to validate serial number
function validateSerialNumber(serialNumber) {
    const serialNumberInput = document.getElementById('serialNumber');
    const serialNumberFeedback = document.getElementById('serialNumberFeedback');
    
    if (!serialNumberFeedback) return;
    
    // Check if it matches Starlink Kit pattern (basic validation)
    const starlinkPattern = /^KIT\d+/;
    const networkPattern = /^\w{4}[\w\d\-]+$/;
    
    if (starlinkPattern.test(serialNumber) || networkPattern.test(serialNumber)) {
        serialNumberInput.classList.remove('is-invalid');
        serialNumberInput.classList.add('is-valid');
        serialNumberFeedback.textContent = 'Serial number format is valid.';
        serialNumberFeedback.className = 'valid-feedback';
    } else {
        serialNumberInput.classList.remove('is-valid');
        serialNumberInput.classList.add('is-invalid');
        serialNumberFeedback.textContent = 'Serial number format does not match expected patterns.';
        serialNumberFeedback.className = 'invalid-feedback';
    }
}

// Function to initialize dashboard charts
function initDashboardCharts() {
    const inventoryChartCanvas = document.getElementById('inventoryStatusChart');
    if (!inventoryChartCanvas) return;
    
    // Example data - in a real application, this would come from the server
    const inventoryData = {
        labels: ['In stock', 'Installed', 'Maintenance', 'Decommissioned'],
        datasets: [{
            label: 'Inventory Status',
            data: [
                parseInt(document.getElementById('inStockCount')?.textContent || 0),
                parseInt(document.getElementById('installedCount')?.textContent || 0),
                parseInt(document.getElementById('maintenanceCount')?.textContent || 0),
                parseInt(document.getElementById('decommissionedCount')?.textContent || 0)
            ],
            backgroundColor: [
                'rgba(25, 135, 84, 0.7)', // green for in stock
                'rgba(13, 110, 253, 0.7)', // blue for installed
                'rgba(253, 126, 20, 0.7)', // orange for maintenance
                'rgba(220, 53, 69, 0.7)'   // red for decommissioned
            ],
            borderColor: [
                'rgb(25, 135, 84)',
                'rgb(13, 110, 253)',
                'rgb(253, 126, 20)',
                'rgb(220, 53, 69)'
            ],
            borderWidth: 1
        }]
    };

    // Only initialize if Chart.js is loaded
    if (typeof Chart !== 'undefined') {
        new Chart(inventoryChartCanvas, {
            type: 'pie',
            data: inventoryData,
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    // Initialize other charts if needed
}

// Function to handle print button
function printReport() {
    window.print();
}

// Function to export table data to CSV
function exportTableToCSV(tableId, filename) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    let csv = [];
    const rows = table.querySelectorAll('tr');
    
    for (let i = 0; i < rows.length; i++) {
        const row = [], cols = rows[i].querySelectorAll('td, th');
        
        for (let j = 0; j < cols.length; j++) {
            // Replace commas with spaces and remove new lines
            let data = cols[j].innerText.replace(/,/g, ' ').replace(/\n/g, ' ');
            // Add double quotes around the data
            row.push('"' + data + '"');
        }
        
        csv.push(row.join(','));
    }
    
    // Download CSV file
    downloadCSV(csv.join('\n'), filename);
}

function downloadCSV(csv, filename) {
    const csvFile = new Blob([csv], {type: 'text/csv'});
    const downloadLink = document.createElement('a');
    
    // File name
    downloadLink.download = filename || 'export.csv';
    // Create a link to the file
    downloadLink.href = window.URL.createObjectURL(csvFile);
    // Hide download link
    downloadLink.style.display = 'none';
    // Add the link to DOM
    document.body.appendChild(downloadLink);
    // Click download link
    downloadLink.click();
    // Remove link from DOM
    document.body.removeChild(downloadLink);
}