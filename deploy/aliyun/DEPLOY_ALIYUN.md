# HireSpark 阿里云 ECS 部署说明

这套说明默认按下面前提编写：

- 服务器系统：Ubuntu 22.04
- 部署目录：`/opt/hirespark`
- 前端对外端口：`80`
- 后端对外端口：`5000`
- 前端域名或公网地址：`http://你的公网 IP`

如果你的服务器不是 Ubuntu，或者你想改成域名 / HTTPS / Docker，我也可以继续帮你调整。

## 一、这套项目怎么部署

这个项目不是纯前端网站，而是：

- 前端：Next.js，默认跑在 `3000`
- 后端：Flask + Socket.IO，默认跑在 `5000`
- Nginx：反向代理前端到 `80`

最终用户访问：

- 网站地址：`http://你的公网IP`

浏览器内部还会访问：

- 后端接口：`http://你的公网IP:5000`

所以阿里云安全组必须至少放行：

- `80/tcp`
- `5000/tcp`

## 二、第一次上服务器要做的事

### 1. 安装基础环境

把仓库里的脚本上传到服务器后执行：

```bash
chmod +x deploy/aliyun/install_ubuntu_2204.sh
./deploy/aliyun/install_ubuntu_2204.sh
```

### 2. 上传项目

推荐两种方式任选一种：

```bash
sudo mkdir -p /opt/hirespark
sudo chown -R $USER:$USER /opt/hirespark
cd /opt
git clone <你的仓库地址> hirespark
```

或者直接把你本地项目打包上传到 `/opt/hirespark`。

## 三、准备生产环境变量

复制模板：

```bash
cd /opt/hirespark
cp deploy/aliyun/.env.production.example .env.production
```

然后编辑：

```bash
nano .env.production
```

重点改这些值：

- `PUBLIC_SITE_URL`
- `NEXT_PUBLIC_BACKEND_URL`
- `NEXT_PUBLIC_API_URL`
- `SOCKETIO_CORS_ALLOWED_ORIGINS`
- `DASHSCOPE_API_KEY` 或 `BAILIAN_API_KEY`
- `AUTH_LOGIN_EMAIL`
- `AUTH_LOGIN_PASSWORD`

如果你暂时只用公网 IP，比如 `47.x.x.x`，那么可以直接写成：

```env
PUBLIC_SITE_URL=http://47.x.x.x
NEXT_PUBLIC_BACKEND_URL=http://47.x.x.x:5000
NEXT_PUBLIC_API_URL=http://47.x.x.x:5000
SOCKETIO_CORS_ALLOWED_ORIGINS=http://47.x.x.x
```

## 四、安装项目依赖

### 1. Python 虚拟环境

```bash
cd /opt/hirespark
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. 前端依赖

```bash
cd /opt/hirespark/frontend
npm install
```

## 五、先手动验证能不能跑起来

### 1. 启动后端

```bash
cd /opt/hirespark
set -a
source .env.production
set +a
source .venv/bin/activate
python backend/app.py
```

看到监听 `0.0.0.0:5000` 后，开另一个终端执行：

```bash
curl http://127.0.0.1:5000/health
```

### 2. 构建并启动前端

```bash
cd /opt/hirespark/frontend
set -a
source ../.env.production
set +a
npm run build
npm run start -- --hostname 0.0.0.0 --port 3000
```

开另一个终端测试：

```bash
curl http://127.0.0.1:3000
```

## 六、配置 systemd 常驻运行

复制服务文件：

```bash
sudo cp /opt/hirespark/deploy/aliyun/hirespark-backend.service /etc/systemd/system/
sudo cp /opt/hirespark/deploy/aliyun/hirespark-frontend.service /etc/systemd/system/
```

重载并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable hirespark-backend
sudo systemctl enable hirespark-frontend
sudo systemctl start hirespark-backend
sudo systemctl start hirespark-frontend
```

查看状态：

```bash
sudo systemctl status hirespark-backend
sudo systemctl status hirespark-frontend
```

查看日志：

```bash
journalctl -u hirespark-backend -f
journalctl -u hirespark-frontend -f
```

## 七、配置 Nginx

复制站点配置：

```bash
sudo cp /opt/hirespark/deploy/aliyun/nginx.hirespark.conf /etc/nginx/sites-available/hirespark
sudo ln -sf /etc/nginx/sites-available/hirespark /etc/nginx/sites-enabled/hirespark
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

## 八、阿里云安全组要放行

在 ECS 控制台安全组里放开：

- `80/tcp`
- `5000/tcp`

如果你以后要上 HTTPS，再放 `443/tcp`。

## 九、最终交付地址

部署成功后，你提交给老师 / 评审的网址可以是：

- `http://你的公网IP`

如果你后面绑定域名，也可以提交域名。

## 十、这套方案的注意点

### 1. 为什么后端单独暴露 5000

因为当前前端里既有 Next 自己的 `/api/auth/*`，又有 Flask 后端的 `/api/*`。
为了不让两套 `/api` 路由打架，当前最稳妥的部署方式就是：

- 前端：`80`
- 后端：`5000`

### 2. TTS 为什么默认关闭

为了先把网站稳定上线。你现在项目功能很多，TTS 额外需要 `5001` 服务，
如果比赛提交时不强依赖语音播报，先关闭最稳。

### 3. 如果你要用域名和 HTTPS

我可以下一步继续帮你补：

- `hirespark.conf` 的 HTTPS 版本
- `api.xxx.com` 的后端子域名方案
- 阿里云证书与备案的配置步骤

