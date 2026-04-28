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

---

## CDN 提供商配置示例

### Cloudflare

#### 缓存规则配置

在 Cloudflare 控制台导航到 **缓存 → 缓存规则**：

**规则 1：绕过 FLV 流**
- **如果**：URI 路径匹配 `/live/*.flv`
- **则**：缓存资格 = 绕过缓存
- **原因**：直播流必须实时，不能缓存

**规则 2：短期缓存 HLS 清单**
- **如果**：URI 路径匹配 `/live/*.m3u8`
- **则**：
  - 缓存资格 = 符合缓存条件
  - 边缘 TTL = 2 秒
  - 浏览器 TTL = 2 秒
- **原因**：清单文件频繁更新

**规则 3：可缓存的 HLS 分片**
- **如果**：URI 路径匹配 `/live/*.ts`
- **则**：
  - 缓存资格 = 符合缓存条件
  - 边缘 TTL = 60 秒
  - 浏览器 TTL = 60 秒
- **原因**：分片一旦创建就不可变

#### 源站配置

导航到 **DNS → 记录**：
- 添加 CNAME：`live-cdn.example.com` → `live-origin.example.com`
- 代理状态：已代理（橙色云朵）

导航到 **SSL/TLS → 源服务器**：
- 源站协议：HTTPS
- 最低 TLS 版本：TLS 1.2

导航到 **网络**：
- WebSockets：开启（用于聊天/观众追踪）
- HTTP/2：开启
- HTTP/3 (QUIC)：开启（可选，提升性能）

---

### AWS CloudFront

#### 分配配置

通过 AWS 控制台或 CloudFormation 创建分配：

```yaml
Resources:
  LiveCDN:
    Type: AWS::CloudFront::Distribution
    Properties:
      DistributionConfig:
        Enabled: true
        Comment: SRS Live Center CDN
        
        Origins:
          - Id: LiveOrigin
            DomainName: live-origin.example.com
            CustomOriginConfig:
              HTTPPort: 80
              HTTPSPort: 443
              OriginProtocolPolicy: https-only
              OriginReadTimeout: 300
              OriginKeepaliveTimeout: 60
        
        DefaultCacheBehavior:
          TargetOriginId: LiveOrigin
          ViewerProtocolPolicy: redirect-to-https
          AllowedMethods: [GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE]
          CachedMethods: [GET, HEAD]
          CachePolicyId: 4135ea2d-6df8-44a3-9df3-4b5a84be39ad  # CachingDisabled
          OriginRequestPolicyId: 216adef6-5c7f-47e4-b989-5492eafa07d3  # AllViewer
        
        CacheBehaviors:
          # FLV 流 - 不缓存
          - PathPattern: /live/*.flv
            TargetOriginId: LiveOrigin
            ViewerProtocolPolicy: redirect-to-https
            CachePolicyId: 4135ea2d-6df8-44a3-9df3-4b5a84be39ad  # CachingDisabled
            
          # HLS 清单 - 2 秒缓存
          - PathPattern: /live/*.m3u8
            TargetOriginId: LiveOrigin
            ViewerProtocolPolicy: redirect-to-https
            CachePolicyId: <custom-policy-id>  # 创建 2 秒 TTL 的自定义策略
            
          # HLS 分片 - 60 秒缓存
          - PathPattern: /live/*.ts
            TargetOriginId: LiveOrigin
            ViewerProtocolPolicy: redirect-to-https
            CachePolicyId: 658327ea-f89d-4fab-a63d-7e88639e58f6  # CachingOptimized
```

#### HLS 清单自定义缓存策略

通过 AWS 控制台 → CloudFront → 策略 → 缓存创建：

- **名称**：`HLS-Manifest-2s`
- **最小 TTL**：0
- **最大 TTL**：2
- **默认 TTL**：2
- **缓存键设置**：包含所有查询字符串

---

### 阿里云 CDN

#### 域名配置

1. 登录阿里云控制台 → CDN → 域名管理
2. 添加域名：`live-cdn.example.com`
3. 业务类型：全站加速
4. 源站信息：
   - 类型：源站域名
   - 域名：`live-origin.example.com`
   - 端口：443
   - 协议：HTTPS

#### 回源配置

导航到 **回源配置**：

- **回源协议**：协议跟随
- **回源 Host**：`live-origin.example.com`
- **回源超时时间**：300 秒
- **回源请求超时**：30 秒

#### 缓存配置

导航到 **缓存配置 → 缓存过期时间**：

| 类型 | 路径 | 过期时间 | 权重 |
|------|------|----------|------|
| 目录 | /live/*.flv | 不缓存 | 90 |
| 目录 | /live/*.m3u8 | 2 秒 | 80 |
| 目录 | /live/*.ts | 60 秒 | 70 |

#### 性能优化

导航到 **性能优化**：

- **页面优化**：关闭（直播流不需要）
- **智能压缩**：关闭（视频已压缩）
- **过滤参数**：关闭（保留所有参数）

---

### 腾讯云 CDN

#### 域名接入

1. 登录腾讯云控制台 → 内容分发网络 CDN
2. 添加域名：`live-cdn.example.com`
3. 所属项目：默认项目
4. 加速区域：中国境内
5. 业务类型：点播加速

#### 源站配置

- **源站类型**：自有源
- **回源协议**：HTTPS
- **源站地址**：`live-origin.example.com`
- **回源 Host**：`live-origin.example.com`
- **源站超时时间**：300 秒

#### 缓存配置

导航到 **缓存配置 → 缓存过期配置**：

```
文件类型：.flv
缓存行为：不缓存
优先级：1

文件类型：.m3u8
缓存时间：2 秒
优先级：2

文件类型：.ts
缓存时间：60 秒
优先级：3
```

---

### Fastly

#### 服务配置

通过 Fastly 控制台或 API 创建服务：

```vcl
# VCL 代码片段用于直播流

sub vcl_recv {
  # 绕过 FLV 流的缓存
  if (req.url ~ "^/live/.*\.flv") {
    return(pass);
  }
}

sub vcl_backend_response {
  # HLS 清单短 TTL
  if (beresp.url ~ "^/live/.*\.m3u8") {
    set beresp.ttl = 2s;
    set beresp.grace = 0s;
  }
  
  # HLS 分片较长 TTL
  if (beresp.url ~ "^/live/.*\.ts") {
    set beresp.ttl = 60s;
    set beresp.grace = 10s;
  }
}
```

#### 后端配置

- **地址**：`live-origin.example.com`
- **端口**：443
- **使用 SSL**：是
- **SNI 主机名**：`live-origin.example.com`
- **连接超时**：5000ms
- **首字节超时**：300000ms（5 分钟）
- **字节间超时**：300000ms

---

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

### Q: CDN 返回 502/504 Gateway Timeout 错误？

**原因**：CDN 的源站超时时间对于长连接的 FLV 流来说太短。

**解决方案**：
1. **增加 CDN 源站超时时间**至 300 秒以上
2. **配置 CDN 不缓冲** FLV 响应（流式传输模式）
3. **验证源站在超时窗口内响应**

**各提供商的修复方法**：
- **Cloudflare**：不推荐用于 FLV（改用源站直连或 HLS）
- **AWS CloudFront**：在分配配置中设置 `OriginReadTimeout: 300`
- **阿里云**：回源配置 → 回源超时时间 → 300 秒
- **Fastly**：设置 `first_byte_timeout` 和 `between_bytes_timeout` 为 300000ms

### Q: 如何验证 CDN 是否真正在提供流量？

**方法 1：检查 HTTP 响应头**
```bash
curl -I https://live-cdn.example.com/live/test.flv

# 查找 CDN 特定的响应头：
# Cloudflare: CF-Cache-Status, CF-Ray
# AWS CloudFront: X-Cache (Hit from cloudfront), X-Amz-Cf-Id
# 阿里云: Ali-Swift-Global-Savetime, X-Cache
# Fastly: X-Cache (HIT, MISS), X-Served-By
```

**方法 2：监控源站带宽**
```bash
# 如果 CDN 正常工作：
# 源站带宽 << 总观众带宽

# 示例：
# 100 个观众 × 2 Mbps = 200 Mbps 总流量
# 源站带宽应 < 10 Mbps（仅缓存未命中）
```

**方法 3：使用 CDN 提供商的分析**
- Cloudflare：分析 → 流量
- AWS CloudFront：监控 → 指标
- 检查"缓存命中率" - HLS 应 >80%，FLV 应为 0%

### Q: FLV 播放通过 CDN 时卡顿或频繁缓冲？

**原因**：CDN 正在缓冲流而不是直接传递。

**解决方案**：
1. **禁用 FLV 的 CDN 缓存**（参见上面的提供商示例）
2. **对 FLV 播放使用源站直连**
3. **切换到 HLS** 以获得 CDN 友好的流式传输

**为什么 FLV 与 CDN 配合不佳**：
- FLV 是长连接的 HTTP 连接（持续数分钟到数小时）
- CDN 边缘节点可能超时或积极缓冲
- HLS 对每个分片使用短连接（对 CDN 更好）

**推荐架构**：
```
FLV 播放 → 源站直连 (live-origin.example.com)
HLS 播放 → CDN (live-cdn.example.com)
```

### Q: 可以同时使用多个 CDN 提供商吗？

**答案**：可以，用于冗余和性能优化。

**设置方法 1：基于 DNS 的负载均衡**
```
live-cdn.example.com → CNAME → cdn-lb.example.com
cdn-lb.example.com → A 记录，多个 IP（轮询）
  - 1.2.3.4 (Cloudflare)
  - 5.6.7.8 (AWS CloudFront)
```

**设置方法 2：前端随机选择**
```typescript
const cdnEndpoints = [
  'https://cdn1.example.com',
  'https://cdn2.example.com',
  'https://cdn3.example.com',
];

const selectedCDN = cdnEndpoints[Math.floor(Math.random() * cdnEndpoints.length)];
const playUrl = `${selectedCDN}/live/${streamName}.flv`;
```

**设置方法 3：基于地理位置的路由**
- 使用具有地理路由的 DNS 服务（Route 53、Cloudflare 负载均衡）
- 将用户路由到最近的 CDN 提供商
- 示例：亚洲 → 阿里云，美国 → AWS CloudFront，欧洲 → Fastly

### Q: 如何处理 CDN 缓存污染或过期内容？

**原因**：CDN 缓存了错误响应或旧内容。

**解决方案**：
1. **清除受影响 URL 的 CDN 缓存**
2. **在源站设置正确的 Cache-Control 头**
3. **对静态资源使用版本化 URL**

**各提供商的清除命令**：
```bash
# Cloudflare
curl -X POST "https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache" \
  -H "Authorization: Bearer {api_token}" \
  -d '{"files":["https://live-cdn.example.com/live/test.flv"]}'

# AWS CloudFront
aws cloudfront create-invalidation \
  --distribution-id E1234567890ABC \
  --paths "/live/test.flv"

# 阿里云
aliyun cdn RefreshObjectCaches \
  --ObjectPath https://live-cdn.example.com/live/test.flv
```

### Q: CDN 带宽成本太高，如何优化？

**优化策略**：

1. **使用 HLS 而不是 FLV**
   - HLS 分片可缓存（减少源站带宽）
   - FLV 需要持续的源站连接

2. **实施自适应比特率**
   - 为慢速连接的用户提供较低质量
   - 减少总带宽消耗

3. **启用 CDN 压缩**
   - 对文本文件使用 Gzip/Brotli（.m3u8 清单）
   - 不要压缩视频（.ts、.flv 已压缩）

4. **设置适当的缓存 TTL**
   - 更长的 TTL = 更高的缓存命中率 = 更低的源站带宽
   - 在新鲜度和成本之间取得平衡

5. **使用定价更优的 CDN**
   - 比较：Cloudflare（固定费率）、AWS（按 GB 付费）、阿里云（CN 优化）
   - 考虑基于成本的路由的多 CDN

### Q: 如何监控 CDN 性能和成本？

**要跟踪的关键指标**：

1. **缓存命中率**
   - 目标：HLS >80%，FLV 0%（绕过）
   - 低命中率 = 浪费的 CDN 成本

2. **源站带宽**
   - 应远低于总观众带宽
   - 高源站带宽 = CDN 未有效工作

3. **延迟（首字节时间）**
   - 对于大多数用户，CDN 应比源站更快
   - 从多个地理位置测试

4. **错误率**
   - 跟踪来自 CDN 的 5xx 错误
   - 高错误率 = 源站问题或 CDN 配置错误

**监控工具**：
```bash
# 持续监控脚本
while true; do
  echo "=== $(date) ==="
  
  # 检查 CDN 响应时间
  time curl -o /dev/null -s https://live-cdn.example.com/live/test.flv
  
  # 检查缓存状态
  curl -I https://live-cdn.example.com/live/test.flv | grep -i cache
  
  sleep 60
done
```

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
