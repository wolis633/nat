"""
nata - not another todo app
使用Flask框架和SQLite数据库实现一个简单的待办事项列表应用
支持添加、删除、标记完成/未完成任务等功能
"""

import webbrowser
from flask import Flask, request, jsonify, render_template, send_file
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
from collections import deque
import json
import yaml
import tempfile

# 创建一个循环缓冲区来存储最近的日志
class LogBuffer:
    def __init__(self, maxlen=100):
        self.buffer = deque(maxlen=maxlen)
    
    def add_log(self, level, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = {
            'timestamp': timestamp,
            'level': level,
            'message': message
        }
        self.buffer.append(log_entry)
    
    def get_logs(self):
        return list(self.buffer)

# 创建全局日志缓冲区
log_buffer = LogBuffer()

# 自定义日志处理器
class BufferHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        log_buffer.add_log(record.levelname, log_entry)

# 创建Flask应用实例
app = Flask(__name__)
# 定义数据库文件名
DB_NAME = 'todos.db'
# 定义端口号
PORT = 12345

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
buffer_handler = BufferHandler()
buffer_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
buffer_handler.setFormatter(formatter)
logger.addHandler(buffer_handler)
app.logger.addHandler(buffer_handler)

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
    app.logger.info("获取所有任务列表")
    
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
    
    app.logger.info(f"成功获取 {len(tasks)} 个任务")
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
    
    # 记录日志
    app.logger.info(f"尝试添加新任务: {title}")
    
    # 验证任务标题
    if not title:
        app.logger.warning("添加任务失败: 任务标题为空")
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
    
    # 记录成功日志
    app.logger.info(f"成功添加任务 ID: {task_id}, 标题: {title}")
    
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
    app.logger.info(f"尝试删除任务 ID: {task_id}")
    
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # 检查任务是否存在
        cursor.execute('SELECT id FROM tasks WHERE id = ?', (task_id,))
        task = cursor.fetchone()
        
        if task is None:
            app.logger.warning(f"删除任务失败: 任务 ID {task_id} 不存在")
            conn.close()
            return jsonify({'error': '任务不存在'}), 404
        
        # 删除指定ID任务的SQL语句
        delete_query = '''
    DELETE FROM tasks 
    WHERE id = ?'''
        cursor.execute(delete_query, (task_id,))
        conn.commit()
        conn.close()
        
        # 记录成功日志
        app.logger.info(f"成功删除任务 ID: {task_id}")
        return '', 204
    except Exception as e:
        # 记录错误并返回
        if conn:
            conn.close()
        app.logger.error(f'删除任务失败: {str(e)}')
        return jsonify({'error': '删除任务失败: ' + str(e)}), 500

# 切换任务完成状态的API接口
@app.route('/api/tasks/<int:task_id>/toggle', methods=['POST'])
def toggle_task(task_id):
    """
    切换指定任务的完成状态
    成功切换返回状态码204 (无内容)
    """
    app.logger.info(f"尝试切换任务状态 ID: {task_id}")
    
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
            app.logger.warning(f"切换任务状态失败: 任务 ID {task_id} 不存在")
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
        
        # 记录成功日志
        status_text = "完成" if new_status else "未完成"
        app.logger.info(f"成功切换任务 ID: {task_id} 状态为: {status_text}")
        return '', 204
    except Exception as e:
        # 记录错误并返回
        if conn:
            conn.close()
        app.logger.error(f'切换任务状态失败: {str(e)}')
        return jsonify({'error': '切换任务状态失败: ' + str(e)}), 500

# 获取日志的API接口
@app.route('/api/logs', methods=['GET'])
def get_logs():
    """
    获取应用日志
    返回最近的日志条目
    """
    return jsonify(log_buffer.get_logs())

# 批量删除任务的API接口
@app.route('/api/tasks/batch-delete', methods=['POST'])
def batch_delete_tasks():
    """
    批量删除任务
    请求体应包含JSON格式数据: {"task_ids": [1, 2, 3]}
    成功删除返回状态码200
    """
    data = request.get_json()
    task_ids = data.get('task_ids', [])
    
    app.logger.info(f"尝试批量删除任务: {task_ids}")
    
    if not task_ids:
        app.logger.warning("批量删除失败: 任务ID列表为空")
        return jsonify({'error': '任务ID列表不能为空'}), 400
    
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # 检查任务是否存在
        placeholders = ','.join(['?' for _ in task_ids])
        cursor.execute(f'SELECT id FROM tasks WHERE id IN ({placeholders})', task_ids)
        existing_tasks = [row[0] for row in cursor.fetchall()]
        
        if len(existing_tasks) != len(task_ids):
            missing_ids = set(task_ids) - set(existing_tasks)
            app.logger.warning(f"批量删除失败: 部分任务不存在 {missing_ids}")
            return jsonify({'error': f'部分任务不存在: {list(missing_ids)}'}), 404
        
        # 批量删除任务
        cursor.execute(f'DELETE FROM tasks WHERE id IN ({placeholders})', task_ids)
        conn.commit()
        conn.close()
        
        app.logger.info(f"成功批量删除 {len(task_ids)} 个任务")
        return jsonify({'message': f'成功删除 {len(task_ids)} 个任务'}), 200
        
    except Exception as e:
        if conn:
            conn.close()
        app.logger.error(f'批量删除任务失败: {str(e)}')
        return jsonify({'error': '批量删除任务失败: ' + str(e)}), 500

# 导出任务包的API接口
@app.route('/api/tasks/export', methods=['POST'])
def export_tasks():
    """
    导出选中的任务为YAML格式的任务包
    请求体应包含JSON格式数据: {"task_ids": [1, 2, 3]}
    返回YAML文件下载
    """
    data = request.get_json()
    task_ids = data.get('task_ids', [])
    
    app.logger.info(f"尝试导出任务包: {task_ids}")
    
    if not task_ids:
        app.logger.warning("导出失败: 任务ID列表为空")
        return jsonify({'error': '任务ID列表不能为空'}), 400
    
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 获取选中的任务
        placeholders = ','.join(['?' for _ in task_ids])
        cursor.execute(f'SELECT * FROM tasks WHERE id IN ({placeholders})', task_ids)
        tasks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if len(tasks) != len(task_ids):
            missing_ids = set(task_ids) - set([task['id'] for task in tasks])
            app.logger.warning(f"导出失败: 部分任务不存在 {missing_ids}")
            return jsonify({'error': f'部分任务不存在: {list(missing_ids)}'}), 404
        
        # 准备导出数据
        export_data = {
            'metadata': {
                'export_time': datetime.now().isoformat(),
                'total_tasks': len(tasks),
                'app_name': 'nata - not another todo app',
                'version': '1.0'
            },
            'tasks': []
        }
        
        # 转换任务数据
        for task in tasks:
            task_data = {
                'id': task['id'],
                'title': task['title'],
                'completed': bool(task['completed']),
                'created_at': task['created_at'],
                'due_date': task['due_date']
            }
            export_data['tasks'].append(task_data)
        
        # 生成YAML内容
        yaml_content = yaml.dump(export_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8')
        temp_file.write(yaml_content)
        temp_file.close()
        
        app.logger.info(f"成功导出 {len(tasks)} 个任务到任务包")
        
        # 返回文件下载
        return send_file(
            temp_file.name,
            as_attachment=True,
            download_name=f'tasks_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.yaml',
            mimetype='application/x-yaml'
        )
        
    except Exception as e:
        if conn:
            conn.close()
        app.logger.error(f'导出任务包失败: {str(e)}')
        return jsonify({'error': '导出任务包失败: ' + str(e)}), 500

# 导入任务包的API接口
@app.route('/api/tasks/import', methods=['POST'])
def import_tasks():
    """
    从YAML文件导入任务包
    请求体应包含multipart/form-data格式的文件
    成功导入返回状态码201
    """
    app.logger.info("尝试导入任务包")
    
    if 'file' not in request.files:
        app.logger.warning("导入失败: 没有上传文件")
        return jsonify({'error': '没有上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        app.logger.warning("导入失败: 文件名为空")
        return jsonify({'error': '文件名为空'}), 400
    
    if not file.filename.lower().endswith(('.yaml', '.yml')):
        app.logger.warning("导入失败: 文件格式不支持")
        return jsonify({'error': '只支持YAML格式文件'}), 400
    
    try:
        # 读取文件内容
        file_content = file.read().decode('utf-8')
        
        # 解析YAML
        try:
            import_data = yaml.safe_load(file_content)
        except yaml.YAMLError as e:
            app.logger.error(f"YAML解析失败: {str(e)}")
            return jsonify({'error': 'YAML文件格式错误: ' + str(e)}), 400
        
        # 验证数据结构
        if not isinstance(import_data, dict) or 'tasks' not in import_data:
            app.logger.error("导入失败: 任务包格式错误")
            return jsonify({'error': '任务包格式错误，缺少tasks字段'}), 400
        
        tasks = import_data['tasks']
        if not isinstance(tasks, list):
            app.logger.error("导入失败: tasks字段不是列表")
            return jsonify({'error': 'tasks字段必须是列表'}), 400
        
        # 导入任务
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        imported_count = 0
        skipped_count = 0
        
        for task_data in tasks:
            # 验证任务数据
            if not isinstance(task_data, dict) or 'title' not in task_data:
                skipped_count += 1
                continue
            
            title = task_data['title'].strip()
            if not title:
                skipped_count += 1
                continue
            
            # 检查是否已存在相同标题的任务
            cursor.execute('SELECT id FROM tasks WHERE title = ?', (title,))
            if cursor.fetchone():
                skipped_count += 1
                continue
            
            # 准备任务数据
            completed = task_data.get('completed', False)
            due_date = task_data.get('due_date', None)
            
            # 插入任务
            cursor.execute(
                'INSERT INTO tasks (title, completed, due_date) VALUES (?, ?, ?)',
                (title, completed, due_date)
            )
            imported_count += 1
        
        conn.commit()
        conn.close()
        
        app.logger.info(f"成功导入 {imported_count} 个任务，跳过 {skipped_count} 个任务")
        
        return jsonify({
            'message': f'成功导入 {imported_count} 个任务',
            'imported_count': imported_count,
            'skipped_count': skipped_count
        }), 201
        
    except Exception as e:
        app.logger.error(f'导入任务包失败: {str(e)}')
        return jsonify({'error': '导入任务包失败: ' + str(e)}), 500

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
    # 在新线程中启动浏览器，避免阻塞应用启动
    webbrowser.open(f'http://localhost:{PORT}')
    app.run(host='0.0.0.0', port=PORT, debug=False)
