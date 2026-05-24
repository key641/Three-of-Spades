# 高德路线字段契约

这份文档说明后端接入高德路线后，会返回哪些统一后的路线字段。B 同学可以用这些字段做路线评分，C 同学可以用这些字段做地图展示。

## 环境变量

```env
AMAP_WEB_SERVICE_KEY=""
```

如果这个 key 为空、无效，或者高德服务暂时不可用，后端会自动使用本地距离估算作为 fallback，并且仍然返回可用于地图展示的字段。

## RouteStop 字段

每个 `RouteStop` 可能包含下面这些字段：

```json
{
  "lat": 31.2304,
  "lng": 121.4737,
  "travel_minutes_from_previous": 16,
  "distance_km_from_previous": 1.2,
  "transport_mode_from_previous": "walk",
  "polyline_from_previous": "121.4737,31.2304;121.4998,31.2397",
  "amap_distance_meters_from_previous": 1200,
  "amap_duration_minutes_from_previous": 16,
  "route_leg_source_from_previous": "amap"
}
```

## 字段说明

- `lat` 和 `lng` 是站点坐标，前端可以用来画地图标记点。
- `travel_minutes_from_previous` 和 `distance_km_from_previous` 是给 B 同学做路线评分和卡片展示的稳定字段。
- `polyline_from_previous` 是从上一个位置到当前站点的路线折线，前端后续可以用它在地图上画线。
- `amap_distance_meters_from_previous` 和 `amap_duration_minutes_from_previous` 保留更细粒度的距离和耗时数据。
- `route_leg_source_from_previous` 表示这段路的数据来源；高德调用成功时是 `amap`，本地估算时是 `fallback`。

## B 同学使用方式

B 同学继续从 `RouteService` 拿路线，不需要直接调高德 API。

评分时建议这样用：

- 总交通耗时：累加每个 stop 的 `travel_minutes_from_previous`。
- 总路线距离：累加每个 stop 的 `distance_km_from_previous`。
- 少走路策略：如果 `transport_mode_from_previous` 是 `walk`，且 `distance_km_from_previous` 较大，就应该扣分。
- 数据可靠性：如果 `route_leg_source_from_previous` 是 `amap`，说明是真实高德路线；如果是 `fallback`，说明是本地估算，评分时可以降低置信度。

目前测试结果显示，高德真实步行耗时会比原来的直线估算更长。后续策略建议：

- 1 公里以内可以保留步行。
- 1 到 5 公里建议考虑骑行、地铁、打车。
- 超过 5 公里不要默认纯步行。
- 用户选择“少走路”“亲子友好”“老人同行”时，应该更早切换到 taxi/metro。

## 后端边界

`AmapService` 负责解析高德原始返回。`RouteService` 只消费统一后的路段字段，不直接依赖高德原始 JSON。
