# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
import sys
from datetime import datetime

# ตั้งค่า encoding สำหรับ Window Terminal
if sys.stdout.encoding != 'utf-8':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# สร้าง Flask app
app = Flask(__name__, template_folder='images/templates', static_folder='images/static')

# ตั้งค่า Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'images/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.secret_key = 'your_secret_key_change_this_in_production'  # สำหรับ Session
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# สร้างโฟลเดอร์ uploads ถ้ายังไม่มี
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# สร้าง Database object
db = SQLAlchemy(app)

# ===== HELPER FUNCTIONS =====
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_unique_filename(filename):
    """สร้างชื่อไฟล์ที่ไม่ซ้ำกัน"""
    name, ext = os.path.splitext(filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
    return timestamp + secure_filename(filename)

# ===== DATABASE MODELS =====
class Product(db.Model):
    """Model สำหรับตาราง Product"""
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    
    def __repr__(self):
        return f'<Product {self.id}: {self.name} - ฿{self.price}>'
    
    def to_dict(self):
        """แปลงเป็น Dictionary สำหรับ JSON"""
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'image_url': self.image_url
        }

# ===== ROUTE =====
@app.route('/')
def index():
    """แสดงหน้าแรก"""
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route('/admin')
def admin():
    """หน้า Admin Panel"""
    products = Product.query.all()
    return render_template('admin.html', products=products)

@app.route('/cart')
def cart():
    """หน้าแสดงตะกร้าสินค้า"""
    return render_template('cart.html')

@app.route('/api/products', methods=['GET'])
def get_products():
    """API ดึงรายการสินค้า"""
    products = Product.query.all()
    return jsonify([p.to_dict() for p in products])

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """API อัปโหลดรูปภาพ"""
    if 'file' not in request.files:
        return jsonify({'error': 'ไม่มีไฟล์'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'ไม่ได้เลือกไฟล์'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'ประเภทไฟล์ไม่ได้รับอนุญาต (png, jpg, jpeg, gif, webp)'}), 400
    
    try:
        filename = get_unique_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        image_url = url_for('static', filename=f'uploads/{filename}', _external=False)
        return jsonify({'image_url': image_url}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products', methods=['POST'])
def add_product():
    """API เพิ่มสินค้า"""
    try:
        # รองรับ JSON data
        data = request.get_json() if request.is_json else request.form.to_dict()
        
        if not data.get('name') or not data.get('price'):
            return jsonify({'error': 'ต้องใส่ชื่อสินค้าและราคา'}), 400
        
        new_product = Product(
            name=data.get('name'),
            price=float(data.get('price')),
            image_url=data.get('image_url', '')
        )
        
        db.session.add(new_product)
        db.session.commit()
        
        return jsonify(new_product.to_dict()), 201
    except ValueError:
        return jsonify({'error': 'ราคาต้องเป็นตัวเลข'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """API ดึงสินค้าตามรหัส"""
    product = Product.query.get_or_404(product_id)
    return jsonify(product.to_dict())

@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """API แก้ไขสินค้า"""
    try:
        product = Product.query.get_or_404(product_id)
        data = request.get_json() if request.is_json else request.form.to_dict()
        
        product.name = data.get('name', product.name)
        if data.get('price'):
            product.price = float(data.get('price'))
        if data.get('image_url'):
            product.image_url = data.get('image_url')
        
        db.session.commit()
        
        return jsonify(product.to_dict())
    except ValueError:
        return jsonify({'error': 'ราคาต้องเป็นตัวเลข'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """API ลบสินค้า"""
    try:
        product = Product.query.get_or_404(product_id)
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({'message': 'ลบสินค้าสำเร็จ'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== CART ROUTES =====
@app.route('/api/cart', methods=['GET'])
def get_cart():
    """API ดึงรายการสินค้าในตะกร้า"""
    cart = session.get('cart', {})
    cart_items = []
    total_price = 0
    
    for product_id, quantity in cart.items():
        product = Product.query.get(int(product_id))
        if product:
            item_total = product.price * quantity
            total_price += item_total
            cart_items.append({
                'id': product.id,
                'name': product.name,
                'price': product.price,
                'image_url': product.image_url,
                'quantity': quantity,
                'item_total': item_total
            })
    
    return jsonify({
        'items': cart_items,
        'total_price': total_price,
        'total_items': sum(cart.values())
    })

@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    """API เพิ่มสินค้าลงตะกร้า"""
    try:
        data = request.get_json()
        product_id = str(data.get('product_id'))
        quantity = int(data.get('quantity', 1))
        
        if not Product.query.get(int(product_id)):
            return jsonify({'error': 'ไม่พบสินค้า'}), 404
        
        # ตรวจสอบ cart ใน session
        if 'cart' not in session:
            session['cart'] = {}
        
        # เพิ่มสินค้า หรือ update quantity
        if product_id in session['cart']:
            session['cart'][product_id] += quantity
        else:
            session['cart'][product_id] = quantity
        
        session.modified = True
        
        return jsonify({
            'message': 'เพิ่มตะกร้าสำเร็จ',
            'cart_count': sum(session.get('cart', {}).values())
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cart/remove/<product_id>', methods=['DELETE'])
def remove_from_cart(product_id):
    """API ลบสินค้าออกจากตะกร้า"""
    try:
        if 'cart' not in session:
            return jsonify({'error': 'ตะกร้าว่าง'}), 400
        
        if product_id in session['cart']:
            del session['cart'][product_id]
            session.modified = True
        
        return jsonify({
            'message': 'ลบสินค้าสำเร็จ',
            'cart_count': sum(session.get('cart', {}).values())
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cart/update/<product_id>', methods=['PUT'])
def update_cart_quantity(product_id):
    """API อัปเดต quantity ในตะกร้า"""
    try:
        data = request.get_json()
        quantity = int(data.get('quantity', 1))
        
        if 'cart' not in session:
            return jsonify({'error': 'ตะกร้าว่าง'}), 400
        
        if product_id not in session['cart']:
            return jsonify({'error': 'ไม่พบสินค้าในตะกร้า'}), 404
        
        if quantity <= 0:
            del session['cart'][product_id]
        else:
            session['cart'][product_id] = quantity
        
        session.modified = True
        
        return jsonify({
            'message': 'อัปเดตตะกร้าสำเร็จ',
            'cart_count': sum(session.get('cart', {}).values())
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cart/clear', methods=['DELETE'])
def clear_cart():
    """API ล้างตะกร้าทั้งหมด"""
    try:
        session.pop('cart', None)
        session.modified = True
        
        return jsonify({'message': 'ล้างตะกร้าสำเร็จ'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== SEED DATABASE =====
def seed_sample_products():
    """เพิ่มข้อมูลสินค้าตัวอย่างลงในฐานข้อมูล ถ้ายังไม่มีสินค้า"""
    with app.app_context():
        # ตรวจสอบว่ามีสินค้าในฐานข้อมูลหรือไม่
        count = Product.query.count()
        
        if count == 0:
            print("📦 ฐานข้อมูลว่างเปล่า กำลังเพิ่มสินค้าตัวอย่าง...")
            
            sample_products = [
                Product(
                    name="หูฟังไร้สาย Wireless Headphones",
                    price=1790.00,
                    image_url="https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400&h=400&fit=crop"
                ),
                Product(
                    name="กล้องดิจิตอล 4K Professional Camera",
                    price=8990.00,
                    image_url="https://images.unsplash.com/photo-1612198188060-c7c2a3b66eae?w=400&h=400&fit=crop"
                ),
                Product(
                    name="สมาร์ทwatch Sport Edition",
                    price=3290.00,
                    image_url="https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400&h=400&fit=crop"
                ),
                Product(
                    name="แท็บเล็ต 10 นิ้ว HD Display",
                    price=6490.00,
                    image_url="https://images.unsplash.com/photo-1561070791-2526d30994b5?w=400&h=400&fit=crop"
                )
            ]
            
            db.session.add_all(sample_products)
            db.session.commit()
            print("✅ เพิ่มสินค้าตัวอย่าง 4 ชิ้นแล้ว!")
        else:
            print(f"✅ มีสินค้าในฐานข้อมูลแล้ว ({count} ชิ้น)")

# ===== CREATE DATABASE =====
def create_database():
    """สร้างไฟล์ database และตำหนา ถ้ายังไม่มี"""
    with app.app_context():
        print("กำลังตรวจสอบ Database...")
        if not os.path.exists('shop.db'):
            print("ยังไม่มีไฟล์ Database สร้างใหม่...")
            db.create_all()
            print("✅ สร้างไฟล์ Database สำเร็จ! (shop.db)")
        else:
            print("✅ ไฟล์ Database มีอยู่แล้ว")

# ===== RUN APPLICATION =====
if __name__ == '__main__':
    # สร้าง database ก่อนรัน server
    create_database()
    
    # เพิ่มข้อมูลสินค้าตัวอย่างถ้าฐานข้อมูลว่าง
    seed_sample_products()
    
    # รัน Flask development server
    print("\n" + "="*50)
    print("🚀 Flask Server กำลังทำงาน...")
    print("📍 http://localhost:5000")
    print("="*50 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
