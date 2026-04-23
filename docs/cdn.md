# CDN 配置指南

> 本文档说明如何在使用 CDN 的情况下正确配置 SRS Live Center，确保 WHIP 推流和 WebRTC 播放功能正常工作。

---

## 核心原则

**WebRTC（WHIP 推流 / WHEP 播放）必须直连源站，不能经过 CDN。**

原因：
- WebRTC 使用 UDP 协议传输媒体数据，CDN 通常只支持 HTTP/HTTPS
- WHIP/WHEP 信令需要与 SRS 服务器直接建立 WebSocket 连接
- ICE 候选交换需要客户端与 SRS 之间的直接网络可达性

---

## 推荐架构

```
┌─────────────┐
│   观众端    │
└──────┬──────┘
       │
       ├─────────────────┐
       │                 │
       │ HTTP-FLV/HLS    │ WebRTC (WHEP)
       │ (可走 CDN)      │ (必须直连)
       │                 │
       ▼                 ▼
   ┌────────┐      ┌──────────┐
   │  CDN   │      │  源站    │
   └───┬────┘      │  SRS     │
       │           └──────────┘
       │ 回源             ▲
       └─────────────────┤
                         │ WHIP 推流
                         │ (必须直连)
                         │
                    ┌────┴────┐
                    │  主播端  │
                    └─────────┘
```

---

## 配置步骤

### 1. 域名规划

建议使用两个域名：

| 域名类型 | 示例 | 用途 | 是否走 CDN |
| --- | --- | --- | --- |
| **CDN 域名** | `live-cdn.example.com` | HTTP-FLV、HLS 播放 | ✅ 是 |
| **源站域名** | `live-origin.example.com` | WHIP 推流、WHEP 播放、管理后台 | ❌ 否 |

### 2. 环境变量配置

```env
# .env

# 源站域名 - 用于 WebRTC 和管理后台
PUBLIC_BASE_URL=https://live-origin.example.com

# 推流域名 - RTMP/SRT 使用，WHIP 会自动使用 PUBLIC_BASE_URL
PUBLISH_BASE_URL=live-origin.example.com

# 其他配置...
CANDIDATE=<SRS 服务器公网 IP>
```

**重要说明：**
- `PUBLIC_BASE_URL` 必须指向**源站**，不能是 CDN 域名
- WHIP 推流 URL 会自动使用 `PUBLIC_BASE_URL`，确保直连源站
- `CANDIDATE` 必须是 SRS 服务器的真实公网 IP（WebRTC ICE 需要）

### 3. Nginx 配置

#### 源站 Nginx（live-origin.example.com）

```nginx
# /etc/nginx/sites-available/live-origin.conf

upstream backend {
    server 127.0.0.1:8000;
}

upstream srs {
    server 127.0.0.1:8080;
}

server {
    listen 443 ssl http2;
    server_name live-origin.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # 管理后台和 API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket (聊天 + 观众心跳)
    location /api/chat/ws/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/viewer/ws/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebRTC 信令 (WHIP 推流 + WHEP 播放)
    location /rtc/ {
        proxy_pass http://srs;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # WHIP/WHEP 需要较长的超时时间
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # HTTP-FLV (源站也提供，供 CDN 回源)
    location /live/ {
        proxy_pass http://srs;
        proxy_set_header Host $host;
        proxy_buffering off;
        
        # FLV 流式传输优化
        proxy_cache off;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        chunked_transfer_encoding on;
        tcp_nopush on;
        tcp_nodelay on;
    }

    # 前端静态资源
    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
    }
}
```

#### CDN 回源配置（live-cdn.example.com）

在 CDN 控制台配置：

1. **回源地址**：`https://live-origin.example.com`
2. **回源 Host**：`live-origin.example.com`
3. **缓存规则**：
   - `/live/*.flv` → **不缓存**（直播流必须实时）
   - `/live/*.m3u8` → 缓存 2 秒
   - `/live/*.ts` → 缓存 60 秒
   - 其他静态资源 → 按需缓存

4. **协议跟随**：开启（客户端用 HTTPS 访问 CDN，CDN 也用 HTTPS 回源）

### 4. 前端播放 URL 配置

前端需要根据播放格式选择不同的域名：

```typescript
// 示例：根据格式选择域名
const getPlayUrl = (format: string, streamName: string) => {
  if (format === 'webrtc') {
    // WebRTC 必须直连源站
    return `https://live-origin.example.com/rtc/v1/whep/?app=live&stream=${streamName}`;
  } else {
    // HTTP-FLV 可以走 CDN
    return `https://live-cdn.example.com/live/${streamName}.flv`;
  }
};
```

**注意**：本项目的播放 URL 由后端生成（`POST /api/streams/play`），后端会根据 `PUBLIC_BASE_URL` 返回正确的 URL。如果需要 FLV 走 CDN，需要在前端手动替换域名。

---

## 验证配置

### 1. 验证 WHIP 推流

```bash
# 使用 ffmpeg 测试 WHIP 推流（必须能直连源站）
ffmpeg -re -i test.mp4 \
  -c:v libx264 -preset veryfast -tune zerolatency -g 30 -bf 0 \
  -c:a libopus -b:a 64k -ar 48000 -ac 2 \
  -f whip "https://live-origin.example.com/rtc/v1/whip/?app=live&stream=test&secret=YOUR_SECRET"
```

**预期结果**：推流成功，无 DNS 解析错误或连接超时。

### 2. 验证 WHEP 播放

在浏览器中访问 `https://live-origin.example.com`，选择 WebRTC 格式播放。

**预期结果**：
- 浏览器控制台无 ICE 连接失败错误
- 播放延迟 < 1 秒

### 3. 验证 HTTP-FLV 走 CDN

```bash
# 测试 CDN 域名的 FLV 播放
curl -I https://live-cdn.example.com/live/test.flv
```

**预期结果**：
- 返回 200 OK
- 响应头包含 CDN 标识（如 `X-Cache: HIT` 或 `Via: CDN-Provider`）

---

## 常见问题

### Q: WHIP 推流失败，提示 "ICE connection failed"？

**原因**：客户端无法与 SRS 服务器建立 UDP 连接。

**排查步骤**：
1. 确认 `CANDIDATE` 环境变量设置为 SRS 服务器的**公网 IP**
2. 确认防火墙开放了 UDP 端口 `8000`（SRS WebRTC 默认端口）
3. 确认 WHIP URL 使用的是源站域名，而非 CDN 域名
4. 使用 `tcpdump` 或 Wireshark 抓包，检查 UDP 8000 端口是否有流量

### Q: 为什么 WHIP 不能走 CDN？

**答**：CDN 是基于 HTTP/HTTPS 的内容分发网络，只能代理 TCP 流量。WebRTC 使用 UDP 协议传输媒体数据，CDN 无法转发 UDP 包。即使 WHIP 信令（HTTP POST）能通过 CDN，后续的 ICE 候选交换和媒体传输仍然需要客户端与 SRS 直连。

### Q: 可以让 HTTP-FLV 走 CDN，WebRTC 走源站吗？

**答**：可以，这正是推荐的架构。配置方法：
1. 前端根据播放格式选择域名（FLV 用 CDN 域名，WebRTC 用源站域名）
2. 或者在 Nginx 层做智能路由（根据 User-Agent 或 URL 参数分流）

### Q: 如何优化 CDN 回源带宽？

**建议**：
1. **启用 SRS 的 HLS 切片**：HLS 的 `.ts` 分片可以被 CDN 缓存，减少回源
2. **使用多 CDN**：配置多个 CDN 节点，分散回源压力
3. **限制 HTTP-FLV 并发**：对于超高并发场景，优先推荐观众使用 HLS（可缓存）而非 FLV（无法缓存）

---

## 参考资料

- [SRS WebRTC 配置文档](https://ossrs.io/lts/zh-cn/docs/v6/doc/webrtc)
- [WHIP 协议规范](https://datatracker.ietf.org/doc/html/draft-ietf-wish-whip)
- [Nginx 反向代理配置](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
