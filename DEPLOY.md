# Linux 服务器部署指南

## 快速部署

### 方法一：使用快速部署脚本（推荐）

```bash
# 1. 进入项目目录
cd /path/to/态势感知

# 2. 赋予执行权限（首次需要）
chmod +x quick_deploy.sh

# 3. 执行部署
./quick_deploy.sh
```

### 方法二：手动部署

```bash
# 1. 进入项目目录
cd /path/to/态势感知

# 2. 拉取最新代码
git pull origin main

# 3. 停止旧进程
ps aux | grep "python.*run_production.py"
kill -9 <PID>

# 4. 启动新进程
nohup python run_production.py > logs/production.log 2>&1 &

# 5. 查看日志
tail -f logs/production.log
```

## 使用 systemd 管理（推荐生产环境）

### 1. 安装服务

```bash
# 复制服务配置文件
sudo cp news-dashboard.service /etc/systemd/system/

# 修改配置文件中的路径
sudo nano /etc/systemd/system/news-dashboard.service
# 将 /path/to/态势感知 改为实际路径

# 创建日志目录
sudo mkdir -p /var/log/news-dashboard
sudo chown www-data:www-data /var/log/news-dashboard

# 重载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start news-dashboard

# 设置开机自启
sudo systemctl enable news-dashboard
```

### 2. 日常管理命令

```bash
# 查看状态
sudo systemctl status news-dashboard

# 启动服务
sudo systemctl start news-dashboard

# 停止服务
sudo systemctl stop news-dashboard

# 重启服务
sudo systemctl restart news-dashboard

# 查看日志
sudo journalctl -u news-dashboard -f

# 或查看文件日志
tail -f /var/log/news-dashboard/output.log
tail -f /var/log/news-dashboard/error.log
```

### 3. 更新部署

```bash
# 进入项目目录
cd /path/to/态势感知

# 拉取最新代码
git pull origin main

# 安装新依赖（如果有）
pip install -r requirements.txt

# 重启服务
sudo systemctl restart news-dashboard

# 查看状态
sudo systemctl status news-dashboard
```

## 使用 Supervisor 管理

### 1. 安装 Supervisor

```bash
sudo apt-get install supervisor
```

### 2. 创建配置文件

```bash
sudo nano /etc/supervisor/conf.d/news-dashboard.conf
```

内容：

```ini
[program:news-dashboard]
command=/usr/bin/python3 /path/to/态势感知/run_production.py
directory=/path/to/态势感知
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/news-dashboard.log
```

### 3. 管理命令

```bash
# 重载配置
sudo supervisorctl reread
sudo supervisorctl update

# 启动
sudo supervisorctl start news-dashboard

# 停止
sudo supervisorctl stop news-dashboard

# 重启
sudo supervisorctl restart news-dashboard

# 查看状态
sudo supervisorctl status news-dashboard

# 查看日志
tail -f /var/log/news-dashboard.log
```

## 使用完整部署脚本

```bash
# 1. 赋予执行权限
chmod +x deploy.sh

# 2. 修改脚本中的项目路径
nano deploy.sh
# 将 PROJECT_DIR="/path/to/态势感知" 改为实际路径

# 3. 执行部署
./deploy.sh
```

## 常见问题

### 1. 端口被占用

```bash
# 查看占用端口的进程
sudo lsof -i :5000
# 或
sudo netstat -tulnp | grep 5000

# 杀掉进程
sudo kill -9 <PID>
```

### 2. MongoDB 连接失败

```bash
# 检查 MongoDB 状态
sudo systemctl status mongodb
# 或
sudo systemctl status mongod

# 启动 MongoDB
sudo systemctl start mongodb
```

### 3. 权限问题

```bash
# 修改项目目录权限
sudo chown -R www-data:www-data /path/to/态势感知

# 或使用当前用户
sudo chown -R $USER:$USER /path/to/态势感知
```

### 4. 查看实时日志

```bash
# 应用日志
tail -f logs/production.log

# 系统日志（systemd）
sudo journalctl -u news-dashboard -f

# Supervisor 日志
tail -f /var/log/news-dashboard.log
```

### 5. 检查服务状态

```bash
# 检查进程
ps aux | grep python

# 检查端口
netstat -tuln | grep 5000

# 测试访问
curl http://localhost:5000
```

## 环境变量配置

如果需要配置环境变量，可以创建 `.env` 文件：

```bash
# 创建环境变量文件
nano .env
```

内容示例：

```bash
FLASK_HOST=0.0.0.0
MONGO_HOST=localhost
MONGO_PORT=27017
SECRET_KEY=your-secret-key-here
```

然后在启动脚本中加载：

```bash
# 加载环境变量
export $(cat .env | xargs)

# 启动应用
python run_production.py
```

## 性能优化建议

1. **使用 Nginx 反向代理**
2. **配置 SSL 证书**
3. **启用 Gzip 压缩**
4. **配置防火墙规则**
5. **定期备份数据库**
6. **监控系统资源**

## 安全建议

1. 修改默认管理员密码
2. 配置防火墙只开放必要端口
3. 使用 HTTPS
4. 定期更新系统和依赖包
5. 配置日志轮转
