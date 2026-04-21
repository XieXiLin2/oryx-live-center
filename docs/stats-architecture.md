# 播放 & 直播统计架构

> **设计原则**：**"播放数据" 由后端自己持久化与计算；"媒体层面的真相" 由 SRS
> 回答。** 这样可以规避 SRS 重启 / 接口字段变动 / 回调偶尔丢失带来的数据漂移。

---

## 1. 责任划分（Who owns what）

| 数据 | 负责方 | 原因 |
| --- | --- | --- |
| **是否正在推流 (`is_live`)** | **SRS** | 只有媒体服务器知道 TCP/UDP 上有没有真的在推流 |
| **视频 / 音频编码 (`video_codec`, `audio_codec`)** | **SRS** | 同上，需要解析 RTMP/WebRTC metadata |
| **当前观众数 (`current_viewers`)** | **后端 (DB)** | 用 `on_play`/`on_stop` 开合 session，比 SRS 自身的 `clients` 更稳定 |
| **累计观看次数 (`total_plays`)** | **后端 (DB)** | 按条插入 `stream_play_sessions`，计数即可 |
| **总观看时长 (`total_watch_seconds`)** | **后端 (DB)** | 每个 session 的 `duration_seconds` 之和 |
| **峰值并发观众 (`peak_session_viewers`)** | **后端 (DB)** | 当前直播区间内的 session 数聚合 |
| **独立登录观众 (`unique_logged_in_viewers`)** | **后端 (DB)** | `COUNT(DISTINCT user_id)` |
| **开播 / 下播时间 (`last_publish_at` / `last_unpublish_at`)** | **后端 (DB)** | `on_publish`/`on_unpublish` 写入 |

---

## 2. 数据流

```
 ┌────────────┐    on_publish / on_unpublish     ┌─────────────────────────┐
 │  推流端     │ ────────────────────────────▶  │ POST /api/hooks/…       │
 │ (OBS/WHIP) │                                  │  → 写 StreamPublish-    │
 └────────────┘                                  │    Session + 更新       │
                                                  │    StreamConfig         │
                                                  └─────────────────────────┘

 ┌────────────┐    on_play  / on_stop            ┌─────────────────────────┐
 │  观众端     │ ────────────────────────────▶  │ POST /api/hooks/…       │
 │ (FLV/WHEP) │                                  │  → 写 StreamPlaySession │
 └────────────┘                                  └─────────────────────────┘

 ┌─────────────────────────────┐ 每 30 秒
 │ stats_reconciler            │ ──轮询──▶ SRS /api/v1/streams, /clients
 │ (后端后台任务)                │            ↓
 │                             │     · 关闭孤儿 publish session
 │                             │     · 关闭孤儿 play session
 │                             │     · 重新计算 viewer_count
 └─────────────────────────────┘

 ┌─────────────────────────────┐
 │ 前端                         │
 │                             │
 │ · GET /api/streams/        │ 每 15s 轮询（列表）
 │ · GET /api/streams/{n}/stats│ 每 10s 轮询（当前房间）
 │                             │
 └─────────────────────────────┘
```

---

## 3. 轮询 vs WebSocket — 为什么选轮询

> **结论**：播放统计采用**后端定时 reconciler + 前端定时轮询**；聊天继续用
> WebSocket。

| 维度 | 轮询（10~15 秒） | WebSocket 推送 |
| --- | --- | --- |
| 数据一致性 | 足够：数据已经最终一致 | 更快 |
| 实现复杂度 | 低 | 需要消息总线 / 房间广播 |
| 跨实例 | 天然支持 | 需要引入 Redis pub/sub |
| 对 SRS 故障容忍 | 下一次轮询自动恢复 | 同理但更复杂 |

对于"当前观众数"、"总时长"这类统计数据，10~15 秒的延迟完全可接受；而这个数字
被成百上千个客户端同时观看，用 WebSocket 推送反而会带来不必要的广播开销。聊天
（实时性要求高、消息量小）则仍然保留 WebSocket。

---

## 4. 核心代码位置

| 文件 | 作用 |
| --- | --- |
| `backend/app/routers/hooks.py` | 接收 SRS 的 4 个 HTTP 回调，写入 session 表 |
| `backend/app/stats_reconciler.py` | 每 30s 与 SRS 对账，关闭孤儿 session，重算 `viewer_count` |
| `backend/app/routers/streams.py` → `list_streams` | 列表接口，其中 `clients` 字段来自 DB，**不再来自 SRS** |
| `backend/app/routers/streams.py` → `get_stream_stats` | `/api/streams/{name}/stats` 单流聚合接口 |
| `frontend/src/pages/Home.tsx` | 每 10s 轮询 `/stats`，展示「当前观众 / 峰值 / 累计次数 / 总时长」 |

---

## 5. 对账（Reconciler）细节

```
每 30 秒：
  A. 拉 SRS 现在有哪些 stream 正在 publish
  B. 拉 SRS 现在有哪些 client_id 还活着

  对每个未关闭的 StreamPublishSession：
    若 A 中不包含该 stream 或其 client_id 已死 → 关闭，duration 按 now - started_at

  对每个未关闭的 StreamPlaySession：
    若 stream 不再在 publish 列表 或 client_id 已死 → 关闭

  对每个 StreamConfig：
    is_live        = (stream_name ∈ 正在 publish 的集合)
    viewer_count   = COUNT(open play sessions WHERE stream_name=...) 或 0
```

> 注意：这里 **不会** 把 SRS 的 `clients` 直接赋给 `viewer_count`。那个数字包含
> publish 本身，也可能在 SRS 短暂抖动时暴涨暴跌。我们只使用自己维护的 session 表。

---

## 6. 一致性保证

| 故障场景 | 行为 |
| --- | --- |
| `on_stop` 丢失（观众浏览器崩溃） | 最多 30s 后 reconciler 发现该 client_id 不在 SRS 了，关闭 session |
| `on_unpublish` 丢失（主播网络断） | 最多 30s 后 reconciler 发现 stream 不在 publish 列表，关闭所有相关 session，并置 `is_live=false` |
| SRS 重启 | 所有 SRS 里的 session 都没了；reconciler 一轮就能关掉所有孤儿并清 0 viewer_count |
| 本后端重启 | session 在表里一直开着；重启后 reconciler 依旧正确关掉它们 |
| 回调被攻击者伪造 | 设置 `SRS_HOOK_SECRET` 后，伪造的 hook 会被拒 |

---

## 7. 前端接口示例

### 列表

```json
GET /api/streams/
{
  "streams": [
    {
      "name": "demo",
      "display_name": "Demo Room",
      "clients": 12,         // ← 来自后端 DB（StreamPlaySession 开箱计数）
      "is_live": true,       // ← 来自 SRS
      "video_codec": "H264", // ← 来自 SRS
      "formats": ["flv", "webrtc"]
    }
  ]
}
```

### 单流聚合

```json
GET /api/streams/demo/stats
{
  "stream_name": "demo",
  "display_name": "Demo Room",
  "is_live": true,
  "current_viewers": 12,
  "total_plays": 3481,
  "total_watch_seconds": 1289400,
  "unique_logged_in_viewers": 420,
  "peak_session_viewers": 37,
  "last_publish_at": "2026-04-21T05:10:22+00:00",
  "last_unpublish_at": "2026-04-20T19:55:10+00:00",
  "current_session_started_at": "2026-04-21T05:10:22+00:00"
}
```

---

## 8. 可扩展方向

想要什么，都基于 `stream_play_sessions` 一张表就能算：

* 每日 / 每周 DAU：`COUNT(DISTINCT user_id) GROUP BY date(started_at)`
* 观看漏斗：按 `duration_seconds` 分桶统计
* 地理分布：加 `client_ip` → GeoIP 聚合（表里已有 `client_ip` 字段）
* 用户总观看时长排行：`SUM(duration_seconds) GROUP BY user_id`

这些都不需要再向 SRS 查询，**数据不会再因为 SRS 自身变化而抖动**。
