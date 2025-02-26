import os
from flask import Flask, request, jsonify
from flask_cors import cross_origin
from flask_cors import CORS
import pymysql
from bcrypt import checkpw, hashpw, gensalt
from datetime import datetime
import pytz  
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy 

app = Flask(__name__)
CORS(app, supports_credentials=True)


# **1. 获取数据库连接的函数**
def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='200461531',
        database='food_order_system',
        cursorclass=pymysql.cursors.DictCursor,
        init_command="SET time_zone='+00:00'",  # 新增时区设置
        charset='utf8mb4',
        autocommit=True
    )

# **2. 登录接口**
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({'success': False, 'message': '账号和密码不能为空'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, password, role FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()

        if user:
            if checkpw(password.encode('utf-8'), user["password"].encode('utf-8')):  # 验证加密密码
                return jsonify({'success': True, 'message': '登录成功', 'user_id': user["id"], 'role': user["role"], 'username': user["username"]})
            else:
                return jsonify({'success': False, 'message': '密码错误'}), 401
        else:
            return jsonify({'success': False, 'message': '用户不存在'}), 401

    except Exception as e:
        print("登录异常:", e)
        return jsonify({'success': False, 'message': '服务器错误，请稍后再试'}), 500
    finally:
        conn.close()


# **3. 注册接口**
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({'success': False, 'message': '账号和密码不能为空'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 检查用户名是否已存在
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            existing_user = cursor.fetchone()

            if existing_user:
                return jsonify({'success': False, 'message': '用户名已存在'}), 400

            # 加密密码
            hashed_password = hashpw(password.encode('utf-8'), gensalt()).decode('utf-8')

            # 插入用户数据
            cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", 
                           (username, hashed_password, 'customer'))
            conn.commit()

        return jsonify({'success': True, 'message': '注册成功'})

    except Exception as e:
        print("注册异常:", e)
        return jsonify({'success': False, 'message': '服务器错误，请稍后再试'}), 500
    finally:
        conn.close()

# **获取所有菜品**
@app.route('/api/dishes', methods=['GET'])
def get_dishes():
    top=request.args.get('top',type=int)
    if top:
        query='SELECT name, price, sales_weekly FROM dishes ORDER BY sales_weekly DESC LIMIT %s'
    else:
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name, price, image_url FROM dishes")
                dishes = cursor.fetchall()  # 获取所有菜品
            print("获取到的菜品:", dishes)  # ✅ 终端打印出来
            return jsonify({'success': True, 'dishes': dishes})
        except Exception as e:
            print("获取菜品失败:", e)
            return jsonify({'success': False, 'message': '获取菜品失败'}), 500
        finally:
            conn.close()


# **删除购物菜品**
@app.route('/api/cart/remove', methods=['POST'])
def remove_from_cart():
    data = request.json
    user_id = data.get("user_id")
    dish_id = data.get("dish_id")
    remark = data.get("remark", "")  # 获取备注

    if not user_id or not dish_id:
        return jsonify({'success': False, 'message': '缺少用户 ID 或菜品 ID'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 先查询当前菜品的数量（确保备注匹配）
        cursor.execute("SELECT quantity FROM cart WHERE user_id = %s AND dish_id = %s AND remark = %s", 
                       (user_id, dish_id, remark))
        cart_item = cursor.fetchone()

        if not cart_item:
            return jsonify({'success': False, 'message': '购物车中没有该菜品'}), 404

        if cart_item["quantity"] > 1:
            # 数量大于 1，减少数量
            cursor.execute("UPDATE cart SET quantity = quantity - 1 WHERE user_id = %s AND dish_id = %s AND remark = %s",
                           (user_id, dish_id, remark))
        else:
            # 数量等于 1，删除该记录
            cursor.execute("DELETE FROM cart WHERE user_id = %s AND dish_id = %s AND remark = %s LIMIT 1",
                           (user_id, dish_id, remark))
        conn.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': '删除失败: ' + str(e)}), 500
    finally:
        conn.close()


# **更新购物车菜品**
@app.route('/api/update_dish', methods=['POST'])
def update_dish():
    data = request.json
    dish_id = data.get("id")
    name = data.get("name")
    price = data.get("price")
    image_url = data.get("image_url")

    if not dish_id or not name or not price or not image_url:
        return jsonify({'success': False, 'message': '菜品信息不完整'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE dishes SET name=%s, price=%s, image_url=%s WHERE id=%s",
                           (name, price, image_url, dish_id))
            conn.commit()
        return jsonify({'success': True, 'message': '菜品更新成功！'})
    except Exception as e:
        print("更新菜品失败:", e)
        return jsonify({'success': False, 'message': '更新菜品失败'}), 500
    finally:
        conn.close()


@app.route('/api/orders', methods=['GET'])
def get_orders():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({'success': False, 'message': '缺少用户ID'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, created_at, status FROM orders WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,)
            )
            orders = cursor.fetchall()
            order_list = []
            
            for order in orders:
                order_id = order['id']
                # 转换时间格式
                created_at = order['created_at'].isoformat() + 'Z'  # 添加UTC时区标识
                cursor.execute("""
                    SELECT d.name, d.price, oi.quantity, oi.note AS remark
                    FROM order_items oi
                    JOIN dishes d ON oi.dish_id = d.id
                    WHERE oi.order_id = %s
                """, (order_id,))

                items = cursor.fetchall()
                
                order_list.append({
                    "order_id": order_id,
                    "created_at": created_at,  # 使用格式化后的时间
                    "status": order["status"],
                    "items": items
                })
                
        return jsonify({'success': True, 'orders': order_list})
    except Exception as e:
        print("获取订单失败:", e)
        return jsonify({'success': False, 'message': '获取订单失败'}), 500
    finally:
        conn.close()


@app.route('/api/submit_order', methods=['POST'])
def submit_order():
    data = request.json
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({'success': False, 'message': '缺少用户ID'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 从购物车中获取该用户的所有记录
            cursor.execute("SELECT dish_id, quantity, remark FROM cart WHERE user_id = %s", (user_id,))
            cart_items = cursor.fetchall()
            if not cart_items:
                return jsonify({'success': False, 'message': '购物车为空'}), 400

            total_price = 0
            # 计算总价（如果 cart 表没有 price 字段，则需要查询 dishes 表）
            for item in cart_items:
                cursor.execute("SELECT price FROM dishes WHERE id = %s", (item['dish_id'],))
                dish = cursor.fetchone()
                if dish:
                    total_price += dish["price"] * item["quantity"]

            # 插入订单记录，状态设置为 pending 或其他状态
            cursor.execute("INSERT INTO orders (user_id, status, total) VALUES (%s, %s, %s)", 
                           (user_id, 'pending', total_price))
            order_id = cursor.lastrowid

            # 插入每一条订单明细
            for item in cart_items:
                cursor.execute(
                    "INSERT INTO order_items (order_id, dish_id, quantity, note) VALUES (%s, %s, %s, %s)",
                    (order_id, item["dish_id"], item["quantity"], item.get("remark", ""))
                )

            # 提交订单后，清空该用户购物车
            cursor.execute("DELETE FROM cart WHERE user_id = %s", (user_id,))

        conn.commit()
        return jsonify({'success': True, 'message': '订单提交成功', 'order_id': order_id})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': '订单提交失败: ' + str(e)}), 500
    finally:
        conn.close()


@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    data = request.json
    user_id = data.get("user_id")
    dish_id = data.get("dish_id")
    quantity = data.get("quantity", 1)  # 默认为 1
    remark = data.get("remark", "").strip()  # 去除前后空格，防止 "少辣 " 和 "少辣" 变成不同备注

    if not user_id or not dish_id:
        return jsonify({'success': False, 'message': '缺少必要的参数'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 获取菜品的图片URL
        cursor.execute("SELECT image_url FROM dishes WHERE id = %s", (dish_id,))
        dish = cursor.fetchone()

        if not dish:
            return jsonify({'success': False, 'message': '菜品不存在'}), 404

        image_url = dish["image_url"]  

        # **检查购物车中是否已有该菜品 + 备注相同**
        cursor.execute(
            "SELECT id, quantity FROM cart WHERE user_id = %s AND dish_id = %s AND remark = %s", 
            (user_id, dish_id, remark)
        )
        cart_item = cursor.fetchone()

        if cart_item:
            # **如果相同菜品+相同备注存在，合并数量**
            cursor.execute(
                "UPDATE cart SET quantity = quantity + %s WHERE id = %s", 
                (quantity, cart_item['id'])
            )
        else:
            # **如果是新的备注，则新增记录**
            cursor.execute(
                "INSERT INTO cart (user_id, dish_id, quantity, remark, image_url) VALUES (%s, %s, %s, %s, %s)",
                (user_id, dish_id, quantity, remark, image_url)
            )

        conn.commit()
        return jsonify({'success': True, 'message': '添加成功'})

    except Exception as e:
        print("添加到购物车失败:", e)
        return jsonify({'success': False, 'message': '添加到购物车失败: ' + str(e)}), 500
    finally:
        conn.close()


@app.route('/api/cart/view', methods=['GET'])
def view_cart():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({'success': False, 'message': '缺少用户ID'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 查询购物车数据
        cursor.execute("""
            SELECT c.dish_id, c.id, c.quantity, c.remark, d.name, d.price, d.image_url
            FROM cart c
            JOIN dishes d ON c.dish_id = d.id
            WHERE c.user_id = %s
        """, (user_id,))

        cart_items = cursor.fetchall()

        return jsonify({'success': True, 'cart_items': cart_items})

    except Exception as e:
        print("查看购物车失败:", e)
        return jsonify({'success': False, 'message': '查看购物车失败: ' + str(e)}), 500
    finally:
        conn.close()

# **新增：管理员添加菜品接口**
@app.route('/api/dishes/add', methods=['POST'])
@cross_origin(supports_credentials=True)
def add_dish():
    # 检查是否有上传图片
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': '未找到图片文件'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择图片文件'}), 400

    # 获取菜品名称和价格
    name = request.form.get('name')
    price = request.form.get('price')
    if not name or not price:
        return jsonify({'success': False, 'message': '菜品名称或价格缺失'}), 400
    try:
        price = float(price)
    except ValueError:
        return jsonify({'success': False, 'message': '价格格式不正确'}), 400

    # 保存图片到静态文件夹
    filename = secure_filename(file.filename)
    upload_folder = 'static/uploads'
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)
    
    # 构造图片的访问 URL（确保前端能通过此 URL 访问图片）
    image_url = f"/{upload_folder}/{filename}"
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 注意这里使用的是 image_url 字段，与你的数据库字段名称一致
            sql = "INSERT INTO dishes (name, price, image_url) VALUES (%s, %s, %s)"
            cursor.execute(sql, (name, price, image_url))
        # 因为 get_db_connection 中 autocommit=True，可不必额外 commit
        return jsonify({'success': True, 'message': '菜品添加成功', 'image_url': image_url})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/orders/admin', methods=['GET'])
@cross_origin(supports_credentials=True)
def get_all_orders_for_admin():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 查询所有订单并关联用户信息
            sql = """
            SELECT o.id AS order_id, o.created_at, o.status, o.total, u.id AS user_id, u.username
            FROM orders o
            JOIN users u ON o.user_id = u.id
            ORDER BY o.created_at DESC
            """
            cursor.execute(sql)
            orders = cursor.fetchall()
            
            order_list = []
            for order in orders:
                order_id = order['order_id']

                cursor.execute("""
                    SELECT d.name, d.price, oi.quantity, oi.note AS remark
                    FROM order_items oi
                    JOIN dishes d ON oi.dish_id = d.id
                    WHERE oi.order_id = %s
                """, (order_id,))

                items = cursor.fetchall()
                
                order_list.append({
                    "order_id": order_id,
                    "created_at": order['created_at'].isoformat() + 'Z',  # 格式化时间
                    "status": order["status"],
                    "total": order["total"],
                    "user_id": order["user_id"],
                    "username": order["username"],
                    "items": items
                })
        return jsonify({'success': True, 'orders': order_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/dishes/<int:dish_id>', methods=['DELETE'])
def delete_dish(dish_id):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM dishes WHERE id = %s", (dish_id,))
            if cursor.rowcount == 0:
                return jsonify({'success': False, 'message': '菜品不存在'}), 404
        # 由于使用 autocommit=True，不必额外调用 conn.commit()
        return jsonify({'success': True, 'message': '菜品删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': '删除失败: ' + str(e)}), 500
    finally:
        conn.close()





# **4. 启动 Flask**a
if __name__ == '__main__':
    app.run(debug=True)