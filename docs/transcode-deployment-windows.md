# Windows 平台转码服务部署补充说明

本文档提供 Windows 平台特定的部署说明和最佳实践。

## Windows 特定注意事项

### 1. WSL 2 vs 原生 Windows 容器

**推荐使用 WSL 2 + Docker Desktop：**
- 更好的 Linux 容器兼容性
- 支持 NVIDIA GPU 加速
- 更接近生产环境（Linux）

**不推荐使用 Windows 容器：**
- FFmpeg 在 Windows 容器中性能较差
- 缺少某些 Linux 特定的编码器
- 生态系统支持有限

### 2. 性能优化

#### 文件系统性能

**最佳实践：**将项目放在 WSL 2 文件系统中，而不是 Windows 文件系统：

```powershell
# 不推荐（慢）
cd C:\Projects\srs-live-center

# 推荐（快）
wsl
cd ~/projects/srs-live-center
```

**原因：**跨文件系统访问（Windows ↔ WSL 2）会显著降低性能。

#### Docker Desktop 资源分配

打开 Docker Desktop 设置 → Resources → Advanced：

- **CPU**：至少 4 核心（推荐 8 核心）
- **Memory**：至少 8GB（推荐 16GB）
- **Swap**：2GB
- **Disk image size**：至少 100GB

### 3. 网络配置

#### WSL 2 网络模式

WSL 2 使用 NAT 网络，可能导致以下问题：

1. **外部无法直接访问 WSL 2 服务**

解决方案：使用端口转发

```powershell
# 转发 WSL 2 的 8080 端口到 Windows
netsh interface portproxy add v4tov4 listenport=8080 listenaddress=0.0.0.0 connectport=8080 connectaddress=$(wsl hostname -I)

# 查看端口转发规则
netsh interface portproxy show all

# 删除端口转发规则
netsh interface portproxy delete v4tov4 listenport=8080 listenaddress=0.0.0.0
```

2. **WSL 2 IP 地址每次重启会变化**

解决方案：使用 `localhost` 或创建自动化脚本

```powershell
# 创建启动脚本 setup-wsl-network.ps1
$wslIp = (wsl hostname -I).Trim()
netsh interface portproxy delete v4tov4 listenport=8080 listenaddress=0.0.0.0
netsh interface portproxy add v4tov4 listenport=8080 listenaddress=0.0.0.0 connectport=8080 connectaddress=$wslIp
Write-Host "WSL 2 IP: $wslIp"
Write-Host "Port forwarding configured for 8080"
```

#### 防火墙配置

Windows Defender 防火墙可能会阻止 Docker 容器网络：

```powershell
# 允许 Docker Desktop 通过防火墙
New-NetFirewallRule -DisplayName "Docker Desktop" -Direction Inbound -Program "C:\Program Files\Docker\Docker\resources\com.docker.backend.exe" -Action Allow

# 允许 WSL 2 网络
New-NetFirewallRule -DisplayName "WSL 2" -Direction Inbound -InterfaceAlias "vEthernet (WSL)" -Action Allow
```

### 4. GPU 加速配置

#### 系统要求

- Windows 11 或 Windows Server 2022
- NVIDIA GPU（支持 CUDA 11.0+）
- NVIDIA 驱动 R470 或更高版本
- WSL 2 内核 5.10.43.3 或更高版本

#### 安装步骤

1. **安装 NVIDIA 驱动**

下载并安装最新的 NVIDIA 驱动：
https://www.nvidia.com/Download/index.aspx

2. **验证 GPU 在 WSL 2 中可用**

```powershell
wsl nvidia-smi
```

如果看到 GPU 信息，说明配置成功。

3. **在 Docker 中启用 GPU**

编辑 `docker-compose.yml`：

```yaml
services:
  transcode-node:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

4. **测试 GPU 加速**

```powershell
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

#### 常见问题

**问题 1：`nvidia-smi` 在 WSL 2 中不可用**

解决方案：
```powershell
# 更新 WSL 2 内核
wsl --update
wsl --shutdown

# 重新启动 WSL 2
wsl
```

**问题 2：Docker 无法识别 GPU**

解决方案：
```powershell
# 重启 Docker Desktop
Stop-Service docker
Start-Service docker

# 或在 Docker Desktop 中点击 "Restart"
```

### 5. 开发环境配置

#### 使用 Windows Terminal

推荐使用 Windows Terminal 进行开发：

```powershell
# 安装 Windows Terminal（如果尚未安装）
winget install Microsoft.WindowsTerminal
```

配置 WSL 2 为默认配置文件：
1. 打开 Windows Terminal
2. 设置 → 启动 → 默认配置文件 → 选择你的 WSL 2 发行版

#### 使用 VS Code

VS Code 提供了优秀的 WSL 2 支持：

```powershell
# 安装 VS Code
winget install Microsoft.VisualStudioCode

# 安装 WSL 扩展
code --install-extension ms-vscode-remote.remote-wsl
```

在 WSL 2 中打开项目：
```bash
cd ~/projects/srs-live-center
code .
```

### 6. 自动化部署

#### 创建部署脚本

创建 `deploy-windows.ps1`：

```powershell
# 部署转码节点到 Windows
param(
    [string]$NodeId = "transcode-windows-01",
    [string]$Region = "beijing",
    [string]$ManagerUrl = "http://localhost:8000",
    [string]$SrsUrl = "rtmp://localhost:1935"
)

Write-Host "部署转码节点: $NodeId" -ForegroundColor Green

# 进入 WSL 2
wsl bash -c @"
cd ~/projects/srs-live-center/transcode-node

# 创建 .env 文件
cat > .env <<EOF
NODE_ID=$NodeId
NODE_NAME=Transcode Node $NodeId
NODE_REGION=$Region
MANAGER_URL=$ManagerUrl
SRS_ORIGIN_URL=$SrsUrl
MAX_TASKS=4
EOF

# 构建并启动
docker-compose build
docker-compose up -d

# 等待服务启动
sleep 5

# 检查状态
docker-compose ps
curl http://localhost:8080/health
"@

Write-Host "部署完成！" -ForegroundColor Green
```

使用脚本：
```powershell
.\deploy-windows.ps1 -NodeId "transcode-beijing-01" -Region "beijing"
```

#### 创建 Windows 服务

将转码节点配置为 Windows 服务，开机自动启动：

1. 安装 NSSM（Non-Sucking Service Manager）：
```powershell
winget install NSSM.NSSM
```

2. 创建服务：
```powershell
nssm install TranscodeNode "C:\Program Files\Docker\Docker\Docker Desktop.exe"
nssm set TranscodeNode AppDirectory "C:\Projects\srs-live-center\transcode-node"
nssm set TranscodeNode Start SERVICE_AUTO_START
```

### 7. 监控和日志

#### 查看 Docker 日志

```powershell
# 实时查看日志
docker-compose logs -f

# 查看最近 100 行日志
docker-compose logs --tail=100

# 查看特定服务的日志
docker-compose logs transcode-node
```

#### 使用 Windows 事件查看器

Docker Desktop 会将错误记录到 Windows 事件日志：

1. 打开"事件查看器"
2. Windows 日志 → 应用程序
3. 筛选来源：Docker Desktop

#### 性能监控

使用 Windows 性能监视器监控资源使用：

```powershell
# 打开性能监视器
perfmon

# 添加计数器：
# - 处理器 → % Processor Time
# - 内存 → Available MBytes
# - 网络接口 → Bytes Total/sec
```

### 8. 故障排查

#### Docker Desktop 无法启动

**症状：**Docker Desktop 启动失败或卡在"Starting..."

**解决方案：**

1. 检查 Hyper-V 是否启用：
```powershell
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V
```

2. 检查 WSL 2 是否正常：
```powershell
wsl --status
```

3. 重置 Docker Desktop：
```powershell
# 停止 Docker Desktop
Stop-Process -Name "Docker Desktop" -Force

# 删除配置文件
Remove-Item -Path "$env:APPDATA\Docker" -Recurse -Force

# 重新启动 Docker Desktop
```

#### 容器无法访问网络

**症状：**容器内无法访问外部网络

**解决方案：**

1. 检查 DNS 配置：
```powershell
wsl cat /etc/resolv.conf
```

2. 修复 DNS（如果需要）：
```bash
# 在 WSL 2 中
sudo rm /etc/resolv.conf
sudo bash -c 'echo "nameserver 8.8.8.8" > /etc/resolv.conf'
sudo chattr +i /etc/resolv.conf
```

3. 重启 WSL 2：
```powershell
wsl --shutdown
```

#### 性能问题

**症状：**转码速度慢，CPU 使用率低

**解决方案：**

1. 增加 Docker Desktop 资源分配
2. 将项目移到 WSL 2 文件系统
3. 禁用 Windows Defender 实时保护（仅开发环境）：
```powershell
# 添加排除路径
Add-MpPreference -ExclusionPath "\\wsl$\Ubuntu\home\user\projects"
```

### 9. 生产环境建议

对于生产环境，建议：

1. **使用 Windows Server 2022**：比 Windows 11 更稳定
2. **使用专用服务器**：不要在开发机上运行生产服务
3. **配置自动重启**：使用 Windows 服务或任务计划程序
4. **监控和告警**：集成 Prometheus + Grafana
5. **定期备份**：备份配置文件和日志
6. **安全加固**：
   - 禁用不必要的 Windows 功能
   - 配置防火墙规则
   - 使用强密码和证书
   - 定期更新系统和 Docker

### 10. 参考资料

- [Docker Desktop for Windows 官方文档](https://docs.docker.com/desktop/windows/)
- [WSL 2 官方文档](https://docs.microsoft.com/en-us/windows/wsl/)
- [NVIDIA GPU 支持 WSL 2](https://docs.nvidia.com/cuda/wsl-user-guide/)
- [Windows Terminal 文档](https://docs.microsoft.com/en-us/windows/terminal/)
