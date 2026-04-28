# 转码服务部署指南

本文档介绍如何部署和配置独立的转码服务架构。

## 架构概述

转码服务采用边缘节点架构，将协议转换和多码率转码任务外置到独立的转码服务器上：

```
推流端(OBS/WHIP) → SRS Origin(仅接收) → 转码节点(协议转换+多码率) → SRS Origin(分发)
                                              ↓
                                         播放端(多协议/多码率)
```

**核心组件：**
- **SRS Origin**：仅负责接收原始推流和分发转码后的流
- **转码节点**：执行协议转换（RTMP→WebRTC、SRT→RTMP）和多码率转码
- **管理服务**：任务调度、节点管理、状态监控

## 系统要求

### 转码节点服务器

**最低配置：**
- CPU：8 核心（推荐 Intel Xeon 或 AMD EPYC）
- 内存：16GB
- 网络：千兆网卡，到 SRS Origin 延迟 < 30ms
- 磁盘：50GB SSD

**推荐配置（GPU 加速）：**
- CPU：16 核心
- 内存：32GB
- GPU：NVIDIA RTX 4060 或更高（用于 NVENC 硬件加速）
- 网络：千兆网卡，到 SRS Origin 延迟 < 30ms
- 磁盘：100GB SSD

**操作系统：**
- Ubuntu 22.04 LTS（推荐）
- Debian 12
- CentOS Stream 9
- Windows Server 2022（支持 Docker Desktop）
- Windows 11 Pro/Enterprise（开发测试环境）

## 部署步骤

### 1. 准备服务器环境

#### Linux 环境

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo apt install docker-compose-plugin -y

# 如果使用 GPU 加速，安装 NVIDIA Docker
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

#### Windows 环境

**系统要求：**
- Windows 11 Pro/Enterprise 或 Windows Server 2022
- 启用 Hyper-V 和 WSL 2
- 至少 8GB 内存（推荐 16GB）

**安装步骤：**

1. **启用 WSL 2**

```powershell
# 以管理员身份运行 PowerShell
wsl --install
wsl --set-default-version 2

# 重启计算机
```

2. **安装 Docker Desktop**

```powershell
# 下载 Docker Desktop for Windows
# https://www.docker.com/products/docker-desktop/

# 安装后启动 Docker Desktop
# 在设置中确保启用 WSL 2 backend
```

3. **配置 Docker Desktop**

打开 Docker Desktop 设置：
- **General**：勾选 "Use the WSL 2 based engine"
- **Resources > WSL Integration**：启用你的 WSL 2 发行版
- **Resources > Advanced**：分配足够的 CPU 和内存（推荐 4 核心，8GB 内存）

4. **安装 NVIDIA GPU 支持（可选）**

如果使用 NVIDIA GPU 进行硬件加速：

```powershell
# 安装 NVIDIA 驱动（最新版本）
# https://www.nvidia.com/Download/index.aspx

# 在 WSL 2 中安装 NVIDIA Container Toolkit
wsl
sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

5. **验证安装**

```powershell
# 在 PowerShell 中验证 Docker
docker --version
docker-compose --version

# 测试 Docker 运行
docker run hello-world

# 如果使用 GPU，测试 GPU 支持
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

### 2. 部署转码节点

#### Linux 环境

```bash
# 克隆代码（或复制 transcode-node 目录）
cd /opt
git clone https://github.com/your-org/srs-live-center.git
cd srs-live-center/transcode-node

# 配置环境变量
cat > .env <<EOF
NODE_ID=transcode-beijing-01
NODE_NAME=Transcode Node Beijing 01
NODE_REGION=beijing
MANAGER_URL=http://your-backend-server:8000
MANAGER_API_KEY=your-api-key-here
SRS_ORIGIN_URL=rtmp://your-srs-server:1935
MAX_TASKS=4
EOF

# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

#### Windows 环境

```powershell
# 克隆代码（或复制 transcode-node 目录）
cd C:\Projects
git clone https://github.com/your-org/srs-live-center.git
cd srs-live-center\transcode-node

# 配置环境变量（创建 .env 文件）
@"
NODE_ID=transcode-beijing-01
NODE_NAME=Transcode Node Beijing 01
NODE_REGION=beijing
MANAGER_URL=http://your-backend-server:8000
MANAGER_API_KEY=your-api-key-here
SRS_ORIGIN_URL=rtmp://your-srs-server:1935
MAX_TASKS=4
"@ | Out-File -FilePath .env -Encoding UTF8

# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

**Windows 特别说明：**

1. **文件路径**：Windows 下使用反斜杠 `\` 或正斜杠 `/` 都可以
2. **行尾符**：确保 `.env` 文件使用 LF 而不是 CRLF（Git 会自动处理）
3. **防火墙**：Windows Defender 防火墙可能会阻止 Docker 容器网络，需要添加规则
4. **性能**：WSL 2 的文件系统性能比原生 Linux 稍慢，建议将项目放在 WSL 2 文件系统中（`\\wsl$\Ubuntu\home\user\projects`）而不是 Windows 文件系统（`C:\Projects`）

### 3. 配置网络

#### Linux 防火墙规则

```bash
# 允许转码节点访问 SRS Origin
sudo ufw allow from <SRS_ORIGIN_IP> to any port 1935 proto tcp
sudo ufw allow from <SRS_ORIGIN_IP> to any port 8000 proto udp

# 允许管理服务访问转码节点
sudo ufw allow from <MANAGER_IP> to any port 8080 proto tcp

# 启用防火墙
sudo ufw enable
```

#### Windows 防火墙规则

```powershell
# 以管理员身份运行 PowerShell

# 允许转码节点访问 SRS Origin（RTMP）
New-NetFirewallRule -DisplayName "SRS RTMP" -Direction Outbound -Protocol TCP -RemotePort 1935 -Action Allow

# 允许转码节点访问 SRS Origin（WebRTC UDP）
New-NetFirewallRule -DisplayName "SRS WebRTC" -Direction Outbound -Protocol UDP -RemotePort 8000 -Action Allow

# 允许管理服务访问转码节点
New-NetFirewallRule -DisplayName "Transcode Node API" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow

# 允许 Docker Desktop 网络
New-NetFirewallRule -DisplayName "Docker Desktop" -Direction Inbound -Program "C:\Program Files\Docker\Docker\resources\com.docker.backend.exe" -Action Allow
```

**Windows 防火墙图形界面配置：**

1. 打开"Windows Defender 防火墙"
2. 点击"高级设置"
3. 选择"入站规则" → "新建规则"
4. 选择"端口" → "TCP" → 输入端口 8080
5. 选择"允许连接"
6. 应用到所有配置文件
7. 命名规则为"Transcode Node API"

**网络优化：**

```bash
# 增加 TCP 缓冲区大小
sudo sysctl -w net.core.rmem_max=134217728
sudo sysctl -w net.core.wmem_max=134217728
sudo sysctl -w net.ipv4.tcp_rmem='4096 87380 67108864'
sudo sysctl -w net.ipv4.tcp_wmem='4096 65536 67108864'

# 启用 TCP BBR 拥塞控制
sudo sysctl -w net.core.default_qdisc=fq
sudo sysctl -w net.ipv4.tcp_congestion_control=bbr

# 持久化配置
sudo tee -a /etc/sysctl.conf <<EOF
net.core.rmem_max=134217728
net.core.wmem_max=134217728
net.ipv4.tcp_rmem=4096 87380 67108864
net.ipv4.tcp_wmem=4096 65536 67108864
net.core.default_qdisc=fq
net.ipv4.tcp_congestion_control=bbr
EOF

sudo sysctl -p
```

### 4. 验证部署

#### Linux 环境

```bash
# 检查容器状态
docker-compose ps

# 检查节点健康状态
curl http://localhost:8080/health

# 检查节点是否已注册到管理服务
curl http://your-backend-server:8000/api/admin/transcode/nodes
```

#### Windows 环境

```powershell
# 检查容器状态
docker-compose ps

# 检查节点健康状态（使用 Invoke-WebRequest）
Invoke-WebRequest -Uri http://localhost:8080/health

# 或使用 curl（Windows 10 1803+ 内置）
curl http://localhost:8080/health

# 检查节点是否已注册到管理服务
Invoke-WebRequest -Uri http://your-backend-server:8000/api/admin/transcode/nodes
```

## 配置说明

### config.yaml

```yaml
node:
  id: transcode-beijing-01          # 节点唯一标识
  name: Transcode Node Beijing 01   # 节点显示名称
  region: beijing                    # 地域标识
  max_tasks: 4                       # 最大并发任务数

manager:
  url: http://localhost:8000         # 管理服务地址
  api_key: your-api-key              # API 密钥
  heartbeat_interval: 10             # 心跳间隔（秒）

srs:
  origin_url: rtmp://localhost:1935  # SRS Origin 地址
  app: live                          # SRS 应用名称

ffmpeg:
  preset: veryfast                   # FFmpeg 编码预设
  tune: zerolatency                  # FFmpeg 调优模式
  gpu_acceleration: false            # 是否启用 GPU 加速

monitoring:
  enabled: true                      # 是否启用监控
  interval: 5                        # 监控间隔（秒）
```

### GPU 加速配置

如果服务器有 NVIDIA GPU，可以启用硬件加速：

1. 修改 `config.yaml`：
```yaml
ffmpeg:
  gpu_acceleration: true
```

2. 确保 `docker-compose.yml` 中已配置 GPU 支持：
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

3. 验证 GPU 可用：
```bash
docker exec transcode-node-01 nvidia-smi
```

## 多地域部署

### 地域规划示例

**北京地域：**
```bash
NODE_ID=transcode-beijing-01
NODE_REGION=beijing
```

**上海地域：**
```bash
NODE_ID=transcode-shanghai-01
NODE_REGION=shanghai
```

**广州地域：**
```bash
NODE_ID=transcode-guangzhou-01
NODE_REGION=guangzhou
```

### 负载均衡策略

管理服务会根据以下策略自动分配任务：
1. **地域优先**：优先分配同地域的转码节点
2. **负载均衡**：同地域内选择负载最低的节点
3. **故障转移**：节点故障时自动切换到其他地域

## 使用指南

### 创建转码配置

1. 登录管理后台：`http://your-domain/admin/transcode-profiles`
2. 点击"新建配置"
3. 填写配置信息：
   - 配置名称：例如 "WebRTC 超低延迟三码率"
   - 源协议：RTMP/SRT/WHIP
   - 延迟模式：ultra_low/low/normal
4. 保存配置

### 创建转码任务

1. 进入"转码任务"页面：`http://your-domain/admin/transcode-tasks`
2. 点击"新建任务"
3. 填写任务信息：
   - 直播间名称：例如 "demo"
   - 转码配置：选择已创建的配置
   - 地域：选择目标地域（可选）
4. 创建后任务会自动启动

### 监控转码节点

1. 进入"转码节点"页面：`http://your-domain/admin/transcode-nodes`
2. 查看节点状态：
   - 在线/离线/繁忙
   - CPU/内存/GPU 使用率
   - 当前任务数
   - 网络延迟

## 故障排查

### 转码节点无法注册

**症状：**节点启动后无法在管理后台看到

**排查步骤：**
1. 检查网络连接：
```bash
curl http://your-backend-server:8000/api/health
```

2. 检查 API 密钥是否正确：
```bash
# 查看节点日志
docker-compose logs transcode-node
```

3. 检查防火墙规则：
```bash
sudo ufw status
```

### 转码任务启动失败

**症状：**任务状态显示为 "failed"

**排查步骤：**
1. 查看任务错误信息：
```bash
curl http://your-backend-server:8000/api/admin/transcode/tasks/{task_id}
```

2. 检查 FFmpeg 日志：
```bash
docker-compose logs transcode-node | grep ffmpeg
```

3. 验证源流地址是否可访问：
```bash
ffprobe rtmp://your-srs-server:1935/live/demo
```

### 转码延迟过高

**症状：**端到端延迟超过 100ms

**优化措施：**
1. 启用 GPU 加速（如果可用）
2. 调整 FFmpeg 参数：
   - 使用 `-preset ultrafast`
   - 减少 GOP 大小：`-g 30`
3. 优化网络：
   - 使用专线或 BGP 多线接入
   - 减少网络跳数
4. 就近部署转码节点

### GPU 加速不工作

**症状：**GPU 使用率为 0

**排查步骤：**

#### Linux 环境

1. 检查 NVIDIA 驱动：
```bash
nvidia-smi
```

2. 检查 Docker GPU 支持：
```bash
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

3. 检查 FFmpeg 是否支持 NVENC：
```bash
docker exec transcode-node-01 ffmpeg -encoders | grep nvenc
```

#### Windows 环境

1. 检查 NVIDIA 驱动：
```powershell
nvidia-smi
```

2. 检查 WSL 2 中的 GPU 支持：
```powershell
wsl nvidia-smi
```

3. 检查 Docker GPU 支持：
```powershell
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

4. 如果 GPU 不可用，检查：
   - NVIDIA 驱动版本是否支持 WSL 2（需要 R470 或更高版本）
   - Docker Desktop 设置中是否启用了 GPU 支持
   - WSL 2 内核版本是否支持 GPU（需要 5.10.43.3 或更高版本）

5. 更新 WSL 2 内核：
```powershell
wsl --update
wsl --shutdown
```

## 性能优化

### CPU 优化

1. **调整并发任务数**：根据 CPU 核心数调整 `max_tasks`
   - 8 核心：max_tasks = 2-3
   - 16 核心：max_tasks = 4-6
   - 32 核心：max_tasks = 8-12

2. **使用更快的编码预设**：
```yaml
ffmpeg:
  preset: ultrafast  # 最快，但质量稍低
```

### GPU 优化

1. **启用 NVENC**：
```yaml
ffmpeg:
  gpu_acceleration: true
```

2. **调整 GPU 预设**：
   - `p1`：最快，质量最低
   - `p4`：平衡
   - `p7`：最慢，质量最高

### 网络优化

1. **启用 TCP BBR**（已在网络配置中说明）
2. **使用 SRT 协议**：比 RTMP 更适合长距离传输
3. **配置 QoS**：优先保证转码流量

## 监控和告警

### Prometheus 指标

转码节点暴露以下指标（端口 8080）：

- `transcode_tasks_total`：总任务数
- `transcode_tasks_running`：运行中的任务数
- `transcode_tasks_failed`：失败的任务数
- `transcode_cpu_usage`：CPU 使用率
- `transcode_memory_usage`：内存使用率
- `transcode_gpu_usage`：GPU 使用率

### Grafana 仪表板

推荐监控指标：
- 转码任务状态分布
- 节点资源使用趋势
- 转码延迟分布
- 任务失败率

### 告警规则

建议配置以下告警：
- 转码节点离线超过 1 分钟
- 转码任务失败率 > 10%
- CPU 使用率 > 90% 持续 5 分钟
- 转码延迟 > 100ms

## 扩容和缩容

### 水平扩容

1. 部署新的转码节点（参考部署步骤）
2. 节点会自动注册到管理服务
3. 新任务会自动分配到新节点

### 垂直扩容

1. 停止转码节点：
```bash
docker-compose down
```

2. 升级服务器配置（CPU/内存/GPU）

3. 调整 `max_tasks` 配置

4. 重启转码节点：
```bash
docker-compose up -d
```

### 缩容

1. 停止接收新任务（在管理后台标记节点为维护模式）
2. 等待现有任务完成
3. 停止并删除节点：
```bash
docker-compose down
```
4. 在管理后台删除节点

## 安全建议

1. **使用 HTTPS**：管理服务和转码节点之间使用 HTTPS 通信
2. **API 密钥管理**：定期轮换 API 密钥
3. **网络隔离**：转码节点部署在独立的 VLAN 中
4. **访问控制**：限制管理后台访问 IP
5. **日志审计**：记录所有转码任务的创建和执行日志

## 成本优化

1. **按需启动**：仅在有观众时启动转码任务
2. **智能码率选择**：根据观众网络质量推荐码率
3. **使用 Spot 实例**：云服务器使用竞价实例降低成本
4. **GPU 共享**：多个转码任务共享同一个 GPU

## 参考资料

- [FFmpeg 官方文档](https://ffmpeg.org/documentation.html)
- [NVIDIA NVENC 编码器指南](https://developer.nvidia.com/nvidia-video-codec-sdk)
- [SRS 官方文档](https://ossrs.net/)
- [Docker 官方文档](https://docs.docker.com/)
