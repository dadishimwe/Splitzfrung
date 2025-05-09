# app.py - Main application file
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime
import csv
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['DATABASE'] = 'zuba_inventory.db'

# Database helper functions
def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with app.app_context():
        db = get_db_connection()
        with open('schema.sql', 'r') as f:
            db.executescript(f.read())
        db.commit()
        db.close()

# User authentication setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, name, role):
        self.id = id
        self.username = username
        self.name = name
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    
    if user is None:
        return None
    
    return User(user['id'], user['username'], user['name'], user['role'])

# Routes
@app.route('/')
@login_required
def index():
    conn = get_db_connection()
    # Get summary counts
    total_items = conn.execute('SELECT COUNT(*) as count FROM items').fetchone()['count']
    in_stock = conn.execute('SELECT COUNT(*) as count FROM items WHERE status = "In stock"').fetchone()['count']
    installed = conn.execute('SELECT COUNT(*) as count FROM items WHERE status = "Installed"').fetchone()['count']
    
    # Get recent activities
    activities = conn.execute('''
        SELECT a.*, u.username, i.serial_number
        FROM activity_log a
        JOIN users u ON a.user_id = u.id
        LEFT JOIN items i ON a.item_id = i.id
        ORDER BY a.timestamp DESC
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return render_template('index.html', 
                          total_items=total_items,
                          in_stock=in_stock,
                          installed=installed,
                          activities=activities)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            user_obj = User(user['id'], user['username'], user['name'], user['role'])
            login_user(user_obj)
            
            # Log the login activity
            conn = get_db_connection()
            conn.execute(
                'INSERT INTO activity_log (user_id, action) VALUES (?, ?)',
                (user['id'], 'Logged in')
            )
            conn.commit()
            conn.close()
            
            return redirect(url_for('index'))
        
        flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    # Log the logout activity
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO activity_log (user_id, action) VALUES (?, ?)',
        (current_user.id, 'Logged out')
    )
    conn.commit()
    conn.close()
    
    logout_user()
    return redirect(url_for('login'))

# Items routes
@app.route('/items')
@login_required
def items_list():
    conn = get_db_connection()
    
    # Get filter parameters
    category_id = request.args.get('category', type=int)
    status = request.args.get('status')
    location_id = request.args.get('location', type=int)
    search = request.args.get('search', '')
    
    # Base query
    query = '''
        SELECT i.*, it.name as item_type, c.name as category, l.name as location
        FROM items i
        JOIN item_types it ON i.item_type_id = it.id
        JOIN categories c ON it.category_id = c.id
        LEFT JOIN locations l ON i.location_id = l.id
        WHERE 1=1
    '''
    params = []
    
    # Add filters
    if category_id:
        query += ' AND it.category_id = ?'
        params.append(category_id)
    
    if status:
        query += ' AND i.status = ?'
        params.append(status)
        
    if location_id:
        query += ' AND i.location_id = ?'
        params.append(location_id)
    
    if search:
        query += ''' AND (
            i.serial_number LIKE ? 
            OR i.model LIKE ? 
            OR it.name LIKE ? 
            OR l.name LIKE ?
            OR i.notes LIKE ?
        )'''
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param, search_param, search_param])
    
    query += ' ORDER BY i.id DESC'
    
    items = conn.execute(query, params).fetchall()
    
    # Get filter options
    categories = conn.execute('SELECT * FROM categories ORDER BY name').fetchall()
    locations = conn.execute('SELECT * FROM locations ORDER BY name').fetchall()
    
    conn.close()
    
    return render_template('items_list.html', 
                          items=items,
                          categories=categories,
                          locations=locations,
                          selected_category=category_id,
                          selected_status=status,
                          selected_location=location_id,
                          search=search)

@app.route('/items/add', methods=['GET', 'POST'])
@login_required
def add_item():
    if current_user.role not in ['admin', 'inventory_manager']:
        flash('You do not have permission to add items')
        return redirect(url_for('items_list'))
    
    if request.method == 'POST':
        # Extract form data
        item_type_id = request.form['item_type_id']
        serial_number = request.form['serial_number']
        model = request.form['model']
        purchase_date = request.form['purchase_date'] or None
        warranty_expiry = request.form['warranty_expiry'] or None
        status = request.form['status']
        location_id = request.form['location_id'] or None
        quantity = request.form['quantity']
        notes = request.form['notes']
        
        conn = get_db_connection()
        
        # Check if serial number already exists
        existing = conn.execute('SELECT id FROM items WHERE serial_number = ?', 
                               (serial_number,)).fetchone()
        if existing:
            conn.close()
            flash('An item with this serial number already exists')
            return redirect(url_for('add_item'))
        
        # Insert the new item
        cursor = conn.execute('''
            INSERT INTO items 
            (item_type_id, serial_number, model, purchase_date, warranty_expiry, 
             status, location_id, quantity, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (item_type_id, serial_number, model, purchase_date, warranty_expiry, 
             status, location_id, quantity, notes))
        
        item_id = cursor.lastrowid
        
        # Log the activity
        conn.execute('''
            INSERT INTO activity_log (user_id, action, item_id)
            VALUES (?, ?, ?)
        ''', (current_user.id, 'Added new item', item_id))
        
        conn.commit()
        conn.close()
        
        flash('Item added successfully')
        return redirect(url_for('items_list'))
    
    conn = get_db_connection()
    item_types = conn.execute('''
        SELECT it.*, c.name as category_name 
        FROM item_types it
        JOIN categories c ON it.category_id = c.id
        ORDER BY c.name, it.name
    ''').fetchall()
    locations = conn.execute('SELECT * FROM locations ORDER BY name').fetchall()
    conn.close()
    
    return render_template('add_item.html', 
                          item_types=item_types,
                          locations=locations)

@app.route('/items/<int:item_id>')
@login_required
def view_item(item_id):
    conn = get_db_connection()
    
    # Get item details
    item = conn.execute('''
        SELECT i.*, it.name as item_type, c.name as category, l.name as location
        FROM items i
        JOIN item_types it ON i.item_type_id = it.id
        JOIN categories c ON it.category_id = c.id
        LEFT JOIN locations l ON i.location_id = l.id
        WHERE i.id = ?
    ''', (item_id,)).fetchone()
    
    if item is None:
        conn.close()
        flash('Item not found')
        return redirect(url_for('items_list'))
    
    # Get maintenance history
    maintenance = conn.execute('''
        SELECT * FROM maintenance_logs
        WHERE item_id = ?
        ORDER BY maintenance_date DESC
    ''', (item_id,)).fetchall()
    
    # Get activity history for this item
    activities = conn.execute('''
        SELECT a.*, u.username
        FROM activity_log a
        JOIN users u ON a.user_id = u.id
        WHERE a.item_id = ?
        ORDER BY a.timestamp DESC
        LIMIT 20
    ''', (item_id,)).fetchall()
    
    conn.close()
    
    return render_template('view_item.html', 
                          item=item,
                          maintenance=maintenance,
                          activities=activities)

@app.route('/items/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    if current_user.role not in ['admin', 'inventory_manager']:
        flash('You do not have permission to edit items')
        return redirect(url_for('view_item', item_id=item_id))
    
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    
    if item is None:
        conn.close()
        flash('Item not found')
        return redirect(url_for('items_list'))
    
    if request.method == 'POST':
        # Extract form data
        item_type_id = request.form['item_type_id']
        serial_number = request.form['serial_number']
        model = request.form['model']
        purchase_date = request.form['purchase_date'] or None
        warranty_expiry = request.form['warranty_expiry'] or None
        status = request.form['status']
        location_id = request.form['location_id'] or None
        quantity = request.form['quantity']
        notes = request.form['notes']
        
        # Check if serial number already exists for another item
        existing = conn.execute('''
            SELECT id FROM items 
            WHERE serial_number = ? AND id != ?
        ''', (serial_number, item_id)).fetchone()
        
        if existing:
            conn.close()
            flash('Another item with this serial number already exists')
            return redirect(url_for('edit_item', item_id=item_id))
        
        # Update the item
        conn.execute('''
            UPDATE items 
            SET item_type_id = ?, serial_number = ?, model = ?, 
                purchase_date = ?, warranty_expiry = ?, status = ?,
                location_id = ?, quantity = ?, notes = ?
            WHERE id = ?
        ''', (item_type_id, serial_number, model, purchase_date, warranty_expiry, 
             status, location_id, quantity, notes, item_id))
        
        # Log the activity
        conn.execute('''
            INSERT INTO activity_log (user_id, action, item_id)
            VALUES (?, ?, ?)
        ''', (current_user.id, 'Updated item', item_id))
        
        conn.commit()
        conn.close()
        
        flash('Item updated successfully')
        return redirect(url_for('view_item', item_id=item_id))
    
    # Get form options
    item_types = conn.execute('''
        SELECT it.*, c.name as category_name 
        FROM item_types it
        JOIN categories c ON it.category_id = c.id
        ORDER BY c.name, it.name
    ''').fetchall()
    locations = conn.execute('SELECT * FROM locations ORDER BY name').fetchall()
    conn.close()
    
    return render_template('edit_item.html', 
                          item=item,
                          item_types=item_types,
                          locations=locations)

# Maintenance routes
@app.route('/maintenance/add/<int:item_id>', methods=['GET', 'POST'])
@login_required
def add_maintenance(item_id):
    if current_user.role not in ['admin', 'inventory_manager', 'technician']:
        flash('You do not have permission to add maintenance records')
        return redirect(url_for('view_item', item_id=item_id))
    
    conn = get_db_connection()
    item = conn.execute('''
        SELECT i.*, it.name as item_type
        FROM items i
        JOIN item_types it ON i.item_type_id = it.id
        WHERE i.id = ?
    ''', (item_id,)).fetchone()
    
    if item is None:
        conn.close()
        flash('Item not found')
        return redirect(url_for('items_list'))
    
    if request.method == 'POST':
        maintenance_date = request.form['maintenance_date']
        description = request.form['description']
        performed_by = request.form['performed_by']
        
        conn.execute('''
            INSERT INTO maintenance_logs 
            (item_id, maintenance_date, description, performed_by)
            VALUES (?, ?, ?, ?)
        ''', (item_id, maintenance_date, description, performed_by))
        
        # Update item status if needed
        new_status = request.form.get('update_status')
        if new_status and new_status != item['status']:
            conn.execute('''
                UPDATE items SET status = ? WHERE id = ?
            ''', (new_status, item_id))
            
            # Log status change
            conn.execute('''
                INSERT INTO activity_log (user_id, action, item_id)
                VALUES (?, ?, ?)
            ''', (current_user.id, f'Changed status to {new_status}', item_id))
        
        # Log maintenance activity
        conn.execute('''
            INSERT INTO activity_log (user_id, action, item_id)
            VALUES (?, ?, ?)
        ''', (current_user.id, 'Added maintenance record', item_id))
        
        conn.commit()
        conn.close()
        
        flash('Maintenance record added successfully')
        return redirect(url_for('view_item', item_id=item_id))
    
    return render_template('add_maintenance.html', item=item)

# Reports routes
@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')

@app.route('/reports/generate', methods=['POST'])
@login_required
def generate_report():
    report_type = request.form['report_type']
    format_type = request.form.get('format', 'html')
    
    conn = get_db_connection()
    
    if report_type == 'inventory_status':
        # Inventory status report
        results = conn.execute('''
            SELECT 
                c.name as category,
                it.name as item_type,
                i.status,
                COUNT(*) as count
            FROM items i
            JOIN item_types it ON i.item_type_id = it.id
            JOIN categories c ON it.category_id = c.id
            GROUP BY c.name, it.name, i.status
            ORDER BY c.name, it.name, i.status
        ''').fetchall()
        
        title = "Inventory Status Report"
        
    elif report_type == 'location_inventory':
        # Location inventory report
        results = conn.execute('''
            SELECT 
                l.name as location,
                c.name as category,
                it.name as item_type,
                COUNT(*) as count
            FROM items i
            JOIN item_types it ON i.item_type_id = it.id
            JOIN categories c ON it.category_id = c.id
            JOIN locations l ON i.location_id = l.id
            GROUP BY l.name, c.name, it.name
            ORDER BY l.name, c.name, it.name
        ''').fetchall()
        
        title = "Location Inventory Report"
        
    elif report_type == 'maintenance_history':
        # Maintenance history report
        results = conn.execute('''
            SELECT 
                i.serial_number,
                it.name as item_type,
                m.maintenance_date,
                m.description,
                m.performed_by
            FROM maintenance_logs m
            JOIN items i ON m.item_id = i.id
            JOIN item_types it ON i.item_type_id = it.id
            ORDER BY m.maintenance_date DESC
        ''').fetchall()
        
        title = "Maintenance History Report"
    
    else:
        conn.close()
        flash('Invalid report type')
        return redirect(url_for('reports'))
    
    conn.close()
    
    if format_type == 'csv':
        # Generate CSV file
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        if results:
            writer.writerow(results[0].keys())
            
            # Write data
            for row in results:
                writer.writerow(row)
        
        response = app.response_class(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={report_type}_{datetime.now().strftime("%Y%m%d")}.csv'}
        )
        return response
    
    else:
        # Display HTML report
        return render_template('report_results.html', 
                              title=title,
                              results=results,
                              report_type=report_type)

# Locations routes
@app.route('/locations')
@login_required
def locations_list():
    conn = get_db_connection()
    locations = conn.execute('''
        SELECT l.*, 
               COUNT(i.id) as item_count,
               SUM(CASE WHEN i.status = 'Installed' THEN 1 ELSE 0 END) as installed_count
        FROM locations l
        LEFT JOIN items i ON l.id = i.location_id
        GROUP BY l.id
        ORDER BY l.name
    ''').fetchall()
    conn.close()
    
    return render_template('locations_list.html', locations=locations)

@app.route('/locations/add', methods=['GET', 'POST'])
@login_required
def add_location():
    if current_user.role not in ['admin', 'inventory_manager']:
        flash('You do not have permission to add locations')
        return redirect(url_for('locations_list'))
    
    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        is_client = 'is_client' in request.form
        contact_person = request.form['contact_person']
        contact_info = request.form['contact_info']
        
        conn = get_db_connection()
        
        # Check if location already exists
        existing = conn.execute('SELECT id FROM locations WHERE name = ?', 
                               (name,)).fetchone()
        if existing:
            conn.close()
            flash('A location with this name already exists')
            return redirect(url_for('add_location'))
        
        # Insert the new location
        conn.execute('''
            INSERT INTO locations 
            (name, address, is_client, contact_person, contact_info)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, address, is_client, contact_person, contact_info))
        
        # Log the activity
        conn.execute('''
            INSERT INTO activity_log (user_id, action)
            VALUES (?, ?)
        ''', (current_user.id, f'Added new location: {name}'))
        
        conn.commit()
        conn.close()
        
        flash('Location added successfully')
        return redirect(url_for('locations_list'))
    
    return render_template('add_location.html')

# User management routes
@app.route('/users')
@login_required
def users_list():
    if current_user.role != 'admin':
        flash('You do not have permission to manage users')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users ORDER BY username').fetchall()
    conn.close()
    
    return render_template('users_list.html', users=users)

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        flash('You do not have permission to add users')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        role = request.form['role']
        
        conn = get_db_connection()
        
        # Check if username already exists
        existing = conn.execute('SELECT id FROM users WHERE username = ?', 
                               (username,)).fetchone()
        if existing:
            conn.close()
            flash('A user with this username already exists')
            return redirect(url_for('add_user'))
        
        # Insert the new user
        password_hash = generate_password_hash(password)
        conn.execute('''
            INSERT INTO users 
            (username, password_hash, name, role)
            VALUES (?, ?, ?, ?)
        ''', (username, password_hash, name, role))
        
        # Log the activity
        conn.execute('''
            INSERT INTO activity_log (user_id, action)
            VALUES (?, ?)
        ''', (current_user.id, f'Added new user: {username}'))
        
        conn.commit()
        conn.close()
        
        flash('User added successfully')
        return redirect(url_for('users_list'))
    
    return render_template('add_user.html')

# Import and export routes
@app.route('/import_export')
@login_required
def import_export():
    if current_user.role not in ['admin', 'inventory_manager']:
        flash('You do not have permission to import/export data')
        return redirect(url_for('index'))
    
    return render_template('import_export.html')

@app.route('/import', methods=['POST'])
@login_required
def import_data():
    if current_user.role not in ['admin', 'inventory_manager']:
        flash('You do not have permission to import data')
        return redirect(url_for('index'))
    
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('import_export'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('import_export'))
    
    if not file.filename.endswith('.csv'):
        flash('Only CSV files are supported')
        return redirect(url_for('import_export'))
    
    import_type = request.form['import_type']
    
    try:
        # Read the CSV file
        stream = io.StringIO(file.stream.read().decode('utf-8'))
        csv_reader = csv.DictReader(stream)
        
        conn = get_db_connection()
        
        if import_type == 'items':
            # Import items
            imported = 0
            skipped = 0
            
            for row in csv_reader:
                # Check if required fields are present
                if not row.get('serial_number') or not row.get('item_type'):
                    skipped += 1
                    continue
                
                # Find or create item type
                category_name = row.get('category', 'Uncategorized')
                item_type_name = row['item_type']
                
                # Get or create category
                category = conn.execute('SELECT id FROM categories WHERE name = ?', 
                                       (category_name,)).fetchone()
                
                if category:
                    category_id = category['id']
                else:
                    cursor = conn.execute('INSERT INTO categories (name) VALUES (?)', 
                                         (category_name,))
                    category_id = cursor.lastrowid
                
                # Get or create item type
                item_type = conn.execute('''
                    SELECT id FROM item_types 
                    WHERE category_id = ? AND name = ?
                ''', (category_id, item_type_name)).fetchone()
                
                if item_type:
                    item_type_id = item_type['id']
                else:
                    cursor = conn.execute('''
                        INSERT INTO item_types (category_id, name) 
                        VALUES (?, ?)
                    ''', (category_id, item_type_name))
                    item_type_id = cursor.lastrowid
                
                # Get or create location
                location_name = row.get('location')
                location_id = None
                
                if location_name:
                    location = conn.execute('SELECT id FROM locations WHERE name = ?', 
                                           (location_name,)).fetchone()
                    
                    if location:
                        location_id = location['id']
                    else:
                        cursor = conn.execute('''
                            INSERT INTO locations (name, is_client) 
                            VALUES (?, ?)
                        ''', (location_name, False))
                        location_id = cursor.lastrowid
                
                # Check if item already exists
                existing = conn.execute('''
                    SELECT id FROM items WHERE serial_number = ?
                ''', (row['serial_number'],)).fetchone()
                
                if existing:
                    # Update existing item
                    conn.execute('''
                        UPDATE items 
                        SET item_type_id = ?, model = ?, status = ?,
                            location_id = ?, quantity = ?, notes = ?
                        WHERE id = ?
                    ''', (
                        item_type_id, 
                        row.get('model', ''),
                        row.get('status', 'In stock'),
                        location_id,
                        int(row.get('quantity', 1)),
                        row.get('notes', ''),
                        existing['id']
                    ))
                else:
                    # Insert new item
                    conn.execute('''
                        INSERT INTO items 
                        (item_type_id, serial_number, model, status, location_id, quantity, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        item_type_id,
                        row['serial_number'],
                        row.get('model', ''),
                        row.get('status', 'In stock'),
                        location_id,
                        int(row.get('quantity', 1)),
                        row.get('notes', '')
                    ))
                    
                imported += 1
            
            # Log the activity
            conn.execute('''
                INSERT INTO activity_log (user_id, action)
                VALUES (?, ?)
            ''', (current_user.id, f'Imported {imported} items ({skipped} skipped)'))
            
            flash(f'Successfully imported {imported} items ({skipped} skipped)')
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        flash(f'Error importing data: {str(e)}')
    
    return redirect(url_for('import_export'))

@app.route('/export/<export_type>')
@login_required
def export_data(export_type):
    if current_user.role not in ['admin', 'inventory_manager']:
        flash('You do not have permission to export data')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    
    if export_type == 'items':
        # Export items
        results = conn.execute('''
            SELECT 
                i.serial_number,
                c.name as category,
                it.name as item_type,
                i.model,
                i.status,
                l.name as location,
                i.quantity,
                i.purchase_date,
                i.warranty_expiry,
                i.notes
            FROM items i
            JOIN item_types it ON i.item_type_id = it.id
            JOIN categories c ON it.category_id = c.id
            LEFT JOIN locations l ON i.location_id = l.id
            ORDER BY c.name, it.name, i.serial_number
        ''').fetchall()
        
        filename = f'zuba_inventory_{datetime.now().strftime("%Y%m%d")}.csv'
    
    elif export_type == 'locations':
        # Export locations
        results = conn.execute('''
            SELECT 
                name,
                address,
                is_client,
                contact_person,
                contact_info
            FROM locations
            ORDER BY name
        ''').fetchall()
        
        filename = f'zuba_locations_{datetime.now().strftime("%Y%m%d")}.csv'
    
    else:
        conn.close()
        flash('Invalid export type')
        return redirect(url_for('import_export'))
    
    conn.close()
    
    # Generate CSV file
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    if results:
        writer.writerow(results[0].keys())
        
        # Write data
        for row in results:
            writer.writerow(row)
    
    response = app.response_class(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )
    return response

# Run the application
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
