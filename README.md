# nata - not another todo app

[nata](https://github.com/wolis633/nat) 是一个基于 Flask 的简单待办事项应用，具有移动端友好的界面和实时同步功能。

![Python](https://img.shields.io/badge/python-3.7%2B-blue)
![Flask](https://img.shields.io/badge/flask-2.0%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## 功能特性

- ✅ 添加、删除、标记完成/未完成任务
- 📱 移动端友好界面，支持手机扫码访问
- ⏰ 任务截止日期设置与提醒
- 🌐 局域网内多设备同步访问
- 📜 实时日志调试面板
- 🗃️ SQLite 数据库存储
- 🌈 视觉反馈（临近截止日期任务高亮显示）

## 快速开始

### 环境要求

- Python 3.7+
- Flask 2.0+
- 其他依赖项（通过 pip 安装）

### 安装步骤

1. 克隆项目：
   ```bash
   git clone https://github.com/wolis633/nat.git
   cd nat
   ```

2. 安装依赖：
   ```bash
   pip install flask qrcode[pil]
   ```

3. 运行应用：
   ```bash
   python app.py
   ```

4. 访问应用：
   - 本地访问：http://localhost:12345
   - 移动端访问：使用同一网络下手机浏览器扫描页面上的二维码

### 使用说明

1. 在输入框中输入任务内容，可选择设置截止日期
2. 点击"添加"按钮创建任务
3. 点击"✅ 完成"按钮标记任务为已完成
4. 点击"↩️ 撤销"按钮将已完成任务标记为未完成
5. 点击"🗑️ 删除"按钮删除任务
6. 页面底部的调试面板可查看应用实时日志

## 技术架构

- **后端**：Python + Flask 框架
- **数据库**：SQLite (todos.db)
- **前端**：原生 HTML + CSS + JavaScript
- **依赖库**：qrcode (生成二维码)

## 项目结构

```
.
├── app.py              # 主应用文件，包含后端逻辑
├── templates/
│   └── index.html      # 前端界面文件
├── todos.db            # SQLite数据库文件
└── README.md           # 项目说明文档
```

## 特色功能详解

### 移动端访问
应用启动后会自动获取本机在局域网中的IP地址，并生成对应的二维码。使用手机扫描该二维码即可在同一网络下访问应用。

### 截止日期提醒
- 任务可设置截止日期
- 临近截止日期的任务背景会逐渐变红
- 已过期任务会以浅红色背景高亮显示

### 调试面板
页面底部提供调试面板，可查看应用的实时日志，便于开发和问题排查。

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 返回主页面 |
| `/api/tasks` | GET | 获取所有任务 |
| `/api/tasks` | POST | 添加新任务 |
| `/api/tasks/<id>` | DELETE | 删除指定任务 |
| `/api/tasks/<id>/toggle` | POST | 切换任务完成状态 |
| `/api/network-info` | GET | 获取网络信息和二维码 |

## 开发指南

1. 项目遵循单文件开发偏好，主要功能实现在 `app.py` 中
2. 数据库操作采用非破坏性、幂等的 ALTER TABLE 方式添加新列
3. 保持现有 API 接口签名不变，确保向后兼容

## 许可证

本项目采用 MIT 许可证，详情请见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进本项目。