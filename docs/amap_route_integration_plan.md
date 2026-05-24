# 高德路线接入规划

## 目标

第一版后端接入的目标，是让路线规划模块能拿到真实地图路线字段，同时不要求路线策略代码直接理解高德原始接口返回。

这一阶段重点做“路段信息补全”：

```text
POI 顺序 -> 查询高德两点之间路线 -> 统一成项目自己的路线字段 -> 路线评分 -> 前端地图展示
```

第一版不追求数学意义上的全局最优路线。我们对外表达的能力是：在不同目标下生成排序最优的候选路线，并带有真实距离、耗时和地图折线数据。

## 当前架构

```text
React 前端
  -> FastAPI /api/chat
  -> Agent 编排层
  -> 用户意图解析
  -> 用户画像
  -> POI 召回
  -> RouteService
  -> ChatResponse 中的 routes
```

当前分工：

- A 同学负责 API 入口、Agent 编排、LLM/provider 接入，以及外部 API 接入。
- B 同学负责 POI 召回、路线候选生成、路线评分和动态重规划策略。
- C 同学负责路线卡片 UI 和地图可视化。

## 目标后端数据流

```text
Intent + 用户画像
  -> POIService 返回带坐标的候选 POI
  -> RouteService 生成候选 POI 顺序
  -> AmapService 补全相邻点之间的真实路段
  -> RouteService 把路段字段写入 RouteStop 和路线总计字段
  -> 评分/重排序逻辑使用统一后的字段
  -> 前端拿到路线卡片数据和地图可视化数据
```

## 为什么要单独拆出 AmapService

高德 Web 服务返回的是高德自己的 JSON 结构。B 同学负责的路线策略不应该依赖这个原始结构，否则后面换接口、补字段、处理异常都会影响路线策略。

`AmapService` 负责：

- 读取 `AMAP_WEB_SERVICE_KEY`。
- 调用高德 Web 服务路线接口。
- 处理超时、没有 key、接口失败等情况。
- 把高德返回结果整理成项目自己的统一字段。
- 当高德不可用时，自动回退到本地距离估算。

`RouteService` 负责：

- 选择 POI 顺序。
- 决定每一段优先使用什么交通方式。
- 应用路线约束和评分策略。
- 把统一后的路段字段写入路线返回结果。

## 统一后的路段字段约定

每一段路线都应该用项目自己的字段表示，而不是直接把高德原始 JSON 丢给 B 或 C：

```json
{
  "mode": "walk",
  "distance_meters": 1200,
  "duration_minutes": 16,
  "polyline": "121.473,31.230;121.480,31.232",
  "steps": [
    {
      "instruction": "沿道路步行",
      "distance_meters": 300,
      "duration_minutes": 4
    }
  ],
  "source": "amap"
}
```

如果没有配置高德 key，或者高德请求失败，服务会返回 fallback 路段：

```json
{
  "mode": "walk",
  "distance_meters": 1200,
  "duration_minutes": 16,
  "polyline": "121.473,31.230;121.480,31.232",
  "steps": [],
  "source": "fallback"
}
```

## 给 B 和 C 使用的路线返回字段

在 `RouteStop` 中新增路线可视化和评分字段：

- `lat`
- `lng`
- `polyline_from_previous`
- `amap_distance_meters_from_previous`
- `amap_duration_minutes_from_previous`
- `route_leg_source_from_previous`

保留原来给 B 评分使用的稳定字段：

- `travel_minutes_from_previous`
- `distance_km_from_previous`
- `transport_mode_from_previous`

这样 B 同学可以继续使用稳定的评分字段，C 同学后续可以用坐标和 polyline 画真实地图路线。

## B 同学具体怎么用

B 同学不需要直接调用高德接口，也不需要读取高德原始 JSON。路线策略里继续使用 `RouteService` 返回的 `RouteStop` 字段即可。

每个站点里和“上一站到当前站”有关的字段如下：

```json
{
  "travel_minutes_from_previous": 23,
  "distance_km_from_previous": 1.7,
  "transport_mode_from_previous": "walk",
  "polyline_from_previous": "121.xxx,31.xxx;121.xxx,31.xxx",
  "amap_distance_meters_from_previous": 1695,
  "amap_duration_minutes_from_previous": 23,
  "route_leg_source_from_previous": "amap"
}
```

字段使用建议：

- 做路线评分时，优先使用 `travel_minutes_from_previous` 和 `distance_km_from_previous`。
- 判断这段数据是否来自真实高德接口，看 `route_leg_source_from_previous`；值为 `amap` 表示高德返回成功，值为 `fallback` 表示使用本地估算。
- 做地图展示时，C 同学使用 `lat`、`lng` 和 `polyline_from_previous`。
- 如果需要更细粒度的原始距离和耗时，可以使用 `amap_distance_meters_from_previous` 和 `amap_duration_minutes_from_previous`。

注意：高德返回的步行耗时通常比我们原来的直线估算更真实，也可能明显更长。因此接入真实路线后，短时间窗内有些候选路线会被过滤掉。B 同学后续可以在策略里加入交通方式切换逻辑，例如：

- 1 公里以内优先步行。
- 1 到 5 公里可以考虑骑行、地铁、打车。
- 超过 5 公里时，不建议继续按纯步行计算。
- 如果用户偏好是“少走路”或“亲子友好”，应更早切换到 taxi/metro。

## 当前链路测试结果

已用上海两点之间的路线测试过后端链路：

```text
高德原始接口返回：
status = 1
infocode = 10000
info = ok
```

通过项目里的 `AmapService` 测试，结果如下：

```text
source = amap
mode = walk
distance_meters = 6080
duration_minutes = 81
polyline_present = true
steps_count = 18
```

通过 `RouteService` 生成路线时，`RouteStop` 也已经能拿到高德字段：

```text
source = amap
distance_km = 1.7 / 4.5 / 2.4
duration_minutes = 23 / 59 / 32
polyline_present = true
lat/lng = true
```

测试时发现：4 小时时间窗下，部分路线因为真实步行耗时变长，会被路线约束过滤；8 小时时间窗可以正常生成路线。这说明高德链路已生效，也提醒后续策略需要考虑交通方式切换。

## 第一版实现范围

第一版只实现“两点之间的路段补全”。

本阶段要做：

- 增加后端配置 `AMAP_WEB_SERVICE_KEY`。
- 增加 `AmapService` 和统一后的路段数据结构。
- 给每个站点补充坐标。
- 给每个路段补充耗时、距离、交通方式、polyline 和数据来源。
- 没有配置高德 key 时安全回退，不影响 demo。
- 更新接口文档和环境变量示例。
- 增加字段契约测试。

本阶段暂不做：

- 前端地图渲染。
- 高德 MCP 接入。
- 全局最优路线算法。
- 实时路况和排队事件。
- 带换乘细节的完整公交/地铁方案。

## 后续扩展方向

这个设计后续可以继续扩展：

- 通过高德搜索或内部 POI 服务增强 POI 召回。
- 对 POI 顺序使用 beam search 或局部搜索。
- 引入类似 OR-Tools 的约束优化算法。
- 根据路况、排队、天气、闭店等事件做动态重规划。
- 把高德 MCP 作为 Agent 工具，用于地点搜索、天气查询和高德 App 唤起链接。
- 前端用高德 JS API 根据 polyline 展示地图路线。

## 验收标准

- 路线站点包含 `lat` 和 `lng`。
- 路段包含统一后的距离、耗时、交通方式、polyline 和数据来源。
- 后端在没有高德 key 的情况下也能通过 fallback 数据正常运行。
- 测试覆盖 fallback 契约和路线返回字段。
- B 同学可以继续使用 `RouteService`，不需要读取高德原始 API 返回。
