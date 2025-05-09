# ZUBA Inventory Management System

A lightweight inventory management system built with Python Flask and SQLite, designed to run on a Raspberry Pi.

## Features

- Track Starlink kits, networking equipment, and other inventory items
- Manage client installations and maintenance history
- Generate inventory reports
- User management with role-based permissions
- Import/export data via CSV
- Activity logging for audit trail

## Requirements

- Raspberry Pi with Raspberry Pi OS (Bullseye or newer)
- Python 3.7+
- Dependencies listed in requirements.txt

## Installation

1. Clone or download this repository to your Raspberry Pi

2. Navigate to the project directory:
   ```bash
   cd zuba_inventory
   ```

3. Make the setup script executable and run it:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
   
4. Follow the prompts to initialize the database and import data.

## Manual Setup (Alternative)

If you prefer to set up manually:

1. Create a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Initialize the database:
   ```bash
   python -c "from app import init_db; init_db()"
   ```

4. Import data from the Excel file (optional):
   ```bash
   python import_data.py "ZUBA Inventory May 2025 Report.xlsx" "zuba_inventory.db"
   ```

5. Run the application:
   ```bash
   python app.py
   ```

## Running as a Service

To configure the application to start automatically on boot:

1. Copy the service file to systemd directory:
   ```bash
   sudo cp zuba_inventory.service /etc/systemd/system/
   ```

2. Start the service:
   ```bash
   sudo systemctl start zuba_inventory
   ```

3. Enable the service to start on boot:
   ```bash
   sudo systemctl enable zuba_inventory
   ```

## Accessing the Application

- Open a web browser and navigate to `http://[raspberry-pi-ip]:5000`
- Log in with the default credentials:
  - Username: `admin`
  - Password: `admin123`
- Be sure to change the default password after first login!

## File Structure

```
/home/pi/zuba_inventory/
├── app.py                  # Main Flask application
├── schema.sql              # SQLite database schema
├── import_data.py          # Script to import data from Excel
├── requirements.txt        # Python dependencies
├── zuba_inventory.db       # SQLite database file
├── ZUBA Inventory May 2025 Report.xlsx  # Original Excel file
├── static/                 # Static files (CSS, JS, images)
├── templates/              # HTML templates
└── venv/                   # Python virtual environment
```

## User Roles

- **Admin**: Full access to all features, including user management
- **Inventory Manager**: Can add/edit inventory and locations, generate reports
- **Technician**: Can view inventory, add maintenance records, update status
- **Viewer**: Read-only access to inventory and reports

## Development

To run the application in development mode:

```bash
export FLASK_APP=app.py
export FLASK_ENV=development
flask run --host=0.0.0.0
```

## License

This project is for internal use at ZUBA.

## Credits

Developed for ZUBA for managing Starlink kits and networking equipment inventory.