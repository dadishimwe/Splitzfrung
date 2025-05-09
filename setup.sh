#!/bin/bash
# Setup script for ZUBA Inventory on Raspberry Pi

echo "Setting up ZUBA Inventory System..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing required packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Initialize database if it doesn't exist
if [ ! -f "zuba_inventory.db" ]; then
    echo "Initializing database..."
    python3 -c "from app import init_db; init_db()"
fi

# Ask if user wants to import data
read -p "Do you want to import data from the Excel file? (y/n): " import_data
if [ "$import_data" = "y" ]; then
    echo "Importing data from Excel file..."
    python3 import_data.py "ZUBA Inventory May 2025 Report.xlsx" "zuba_inventory.db"
fi

# Create systemd service file
echo "Creating systemd service file..."
cat <<EOF > zuba_inventory.service
[Unit]
Description=ZUBA Inventory System
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/gunicorn -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Instructions for installing the service
echo ""
echo "===== Installation Complete ====="
echo ""
echo "To start the application manually:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Run the app: python app.py"
echo ""
echo "To set up as a service that starts automatically:"
echo "1. Copy the service file to systemd: sudo cp zuba_inventory.service /etc/systemd/system/"
echo "2. Start the service: sudo systemctl start zuba_inventory"
echo "3. Enable autostart: sudo systemctl enable zuba_inventory"
echo ""
echo "The web interface will be available at: http://raspberry-pi-ip:5000"
echo "Default login credentials:"
echo "Username: admin"
echo "Password: admin123"
echo ""
echo "Please change the default password after first login."