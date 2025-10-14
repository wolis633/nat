"""
nata - not another todo app
使用Flask框架和SQLite数据库实现一个简单的待办事项列表应用
支持添加、删除、标记完成/未完成任务等功能
"""

from flask import Flask, request, jsonify, render_template
import sqlite3
import os
import socket
import qrcode
from io import BytesIO
import base64
import logging
from datetime import datetime, timedelta
import subprocess
import signal

# 创建Flask应用实例
app = Flask(__name__)
# 定义数据库文件名
DB_NAME = 'todos.db'
# 定义端口号
PORT = 12345

# 获取本机内网IP地址
def get_local_ip():
    """
    获取本机在局域网中的IP地址
    """
    try:
        # 创建一个UDP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 连接到一个远程地址（不会真正发送数据）
        s.connect(("8.8.8.8", 80))
        # 获取本地IP地址
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # 如果无法获取IP，返回localhost
        return "127.0.0.1"

# 检查并终止占用端口的进程
def kill_port_process(port):
    """
    检查指定端口是否被占用，如果被占用则终止占用进程
    """
    try:
        # 使用lsof命令查找占用指定端口的进程
        result = subprocess.run(['lsof', '-i', f':{port}'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout:
            # 解析输出，获取进程ID
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # 第一行是标题，从第二行开始是进程信息
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 2:
                        pid = parts[1]
                        try:
                            # 终止进程
                            os.kill(int(pid), signal.SIGTERM)
                            print(f"已终止占用端口{port}的进程 (PID: {pid})")
                        except (ValueError, ProcessLookupError):
                            pass
    except Exception as e:
        print(f"检查/终止端口进程时出错: {e}")

# 生成二维码
def generate_qr_code(url):
    """
    生成指定URL的二维码并返回base64编码的图片数据
    """
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # 将图片转换为base64编码
    buffer = BytesIO()
    img.save(buffer, "PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return img_str

# 初始化数据库
def init_db():
    """
    初始化SQLite数据库，创建tasks表
    表结构包含：
    - id: 任务唯一标识符，主键，自增
    - title: 任务标题，非空文本
    - completed: 任务完成状态，布尔值，默认为0(未完成)
    - created_at: 任务创建时间戳，默认为当前时间
    - due_date: 任务到期时间，可为空
    """
    conn = sqlite3.connect(DB_NAME)
    
    # 检查tasks表是否存在due_date字段
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(tasks)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'due_date' not in columns:
        # 如果due_date字段不存在，则添加该字段
        cursor.execute("ALTER TABLE tasks ADD COLUMN due_date TIMESTAMP NULL")
    
    # 如果tasks表不存在，则创建表
    create_table_query = '''
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    completed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date TIMESTAMP NULL
)'''
    conn.execute(create_table_query)
    conn.commit()
    conn.close()

# 应用根路径路由，返回HTML页面
@app.route('/')
def index():
    """
    处理根路径请求，返回任务管理器主页面
    """
    return render_template('index.html')

# 获取网络信息的API接口
@app.route('/api/network-info')
def get_network_info():
    """
    获取当前网络信息，包括IP地址、端口和二维码
    """
    # 获取本地IP和端口
    local_ip = get_local_ip()
    port = PORT
    # 构造完整的访问URL
    url = f"http://{local_ip}:{port}"
    # 生成二维码
    qr_code = generate_qr_code(url)
    
    # 返回JSON格式的网络信息
    return jsonify({
        'local_ip': local_ip,
        'port': port,
        'url': url,
        'qr_code': qr_code
    })

# 获取所有任务的API接口
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """
    获取所有任务
    返回所有任务的JSON数组，按到期时间排序（未设置到期时间的任务排在最后）
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # 查询所有任务，按到期时间排序（NULL值排在最后）
    select_query = '''
SELECT * 
FROM tasks 
ORDER BY 
    CASE 
        WHEN due_date IS NULL THEN 1 
        ELSE 0 
    END,
    due_date ASC,
    created_at DESC'''
    cursor.execute(select_query)
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(tasks)

# 添加新任务的API接口
@app.route('/api/tasks', methods=['POST'])
def add_task():
    """
    添加新任务
    请求体应包含JSON格式数据: {"title": "任务标题", "due_date": "YYYY-MM-DD HH:MM:SS"}
    成功返回新创建的任务信息，状态码201
    """
    data = request.get_json()
    title = data.get('title', '').strip()
    due_date = data.get('due_date', None)
    
    # 验证任务标题
    if not title:
        return jsonify({'error': '任务标题不能为空'}), 400
    
    # 插入新任务到数据库
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # 插入新任务的SQL语句
    insert_query = '''
INSERT INTO tasks (title, due_date) 
VALUES (?, ?)'''
    cursor.execute(insert_query, (title, due_date))
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    
    # 返回新创建的任务信息
    return jsonify({
        'id': task_id, 
        'title': title, 
        'completed': False,
        'due_date': due_date
    }), 201

# 删除任务的API接口
@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """
    根据任务ID删除指定任务
    成功删除返回状态码204 (无内容)
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # 检查任务是否存在
        cursor.execute('SELECT id FROM tasks WHERE id = ?', (task_id,))
        task = cursor.fetchone()
        
        if task is None:
            conn.close()
            return jsonify({'error': '任务不存在'}), 404
        
        # 删除指定ID任务的SQL语句
        delete_query = '''
    DELETE FROM tasks 
    WHERE id = ?'''
        cursor.execute(delete_query, (task_id,))
        conn.commit()
        conn.close()
        return '', 204
    except Exception as e:
        # 记录错误并返回
        if conn:
            conn.close()
        app.logger.error('删除任务失败: %s', str(e))
        return jsonify({'error': '删除任务失败: ' + str(e)}), 500

# 切换任务完成状态的API接口
@app.route('/api/tasks/<int:task_id>/toggle', methods=['POST'])
def toggle_task(task_id):
    """
    切换指定任务的完成状态
    成功切换返回状态码204 (无内容)
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # 查询指定ID任务当前状态的SQL语句
        select_query = '''
SELECT completed 
FROM tasks 
WHERE id = ?'''
        cursor.execute(select_query, (task_id,))
        task = cursor.fetchone()
        if task is None:
            conn.close()
            return jsonify({'error': '任务不存在'}), 404
        
        # 切换任务完成状态 (0变1，1变0)
        new_status = not task[0]
        # 更新任务状态的SQL语句
        update_query = '''
UPDATE tasks 
SET completed = ? 
WHERE id = ?'''
        cursor.execute(update_query, (new_status, task_id))
        conn.commit()
        conn.close()
        return '', 204
    except Exception as e:
        # 记录错误并返回
        if conn:
            conn.close()
        app.logger.error('切换任务状态失败: %s', str(e))
        return jsonify({'error': '切换任务状态失败: ' + str(e)}), 500

# 应用入口点
if __name__ == '__main__':
    """
    程序入口点
    1. 检查并终止占用端口的进程
    2. 初始化数据库
    3. 启动Flask开发服务器，监听所有网络接口的12345端口
    """
    # 检查并终止占用端口的进程
    kill_port_process(PORT)
    
    # 初始化数据库
    init_db()
    
    # 启动应用（禁用调试模式避免重启问题）
    app.run(host='0.0.0.0', port=PORT, debug=False)
