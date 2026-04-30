## 后端函数调用图（文本版）

```text
用户请求
  ↓
Frontend /api/search
  ↓
backend/api/search.py
  search_flights(payload, request)
  ↓
app.state.search_service.search(user_id, message)
  ├─ 1. UnifiedLLMClient.parse_intent(message)
  │      ↓
  │    解析出 origin / destination / date_start / date_end / budget
  │
  ├─ 2. SearchService._get_preferences(user_id)
  │      ↓
  │    LongTermMemory.get_preferences(user_id)
  │
  ├─ 3. DataSourceRegistry.get("ctrip")
  │      ↓
  │    CtripSource.search_flights(origin, destination, date_start, date_end)
  │      ├─ _try_third_party_search(...)
  │      │    └─ retry_with_backoff → asyncio.to_thread → CtripFlightClient.search_oneway(...)
  │      └─ 第三方失败时：_build_mock_results(...)
  │
  ├─ 4. compare_prices(flights)
  ├─ 5. CtripSource.get_history_prices(route, days=90)
  ├─ 6. analyze_history(history_prices, min_price)
  ├─ 7. match_preference(flights, preferences, query)
  ├─ 8. generate_signals(comparison, history, preference)
  │
  ├─ 9. UnifiedLLMClient.generate_recommendation(...)
  │      ↓
  │    生成 recommendation / confidence / signals
  │
  └─ 10. 组装 SearchResponseDto 所需字段
         ↓
       返回搜索结果给前端
```

```text
记忆链路

Frontend /api/memory
  ↓
backend/api/memory.py
  ├─ GET    → RecommendationService.get_memory(user_id)
  │            ├─ LongTermMemory.get_preferences(user_id)
  │            ├─ LongTermMemory.get_recent_queries(user_id)
  │            └─ LongTermMemory.get_recent_clicks(user_id)
  │
  ├─ PATCH  → RecommendationService.patch_memory(user_id, field, value)
  │            └─ LongTermMemory.upsert_preferences(...)
  │
  └─ DELETE → RecommendationService.delete_memory_field(user_id, field)
               └─ LongTermMemory.upsert_preferences(...)
```

```text
推荐链路

Frontend /api/recommendations
  ↓
backend/api/recommendations.py
  ↓
RecommendationService.get_cards(user_id)
  ├─ LongTermMemory.get_preferences(user_id)
  ├─ 生成热门低价机会卡片
  ├─ 根据 frequent_destinations 生成个性化卡片
  └─ 返回 recommendations 响应
```

## 后端整体架构图（文本版）

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                Frontend / Next.js                           │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI App  (backend/main.py)                      │
│  create_app() + lifespan()                                                  │
│  - 初始化 engine / session_factory                                          │
│  - 初始化 redis_client                                                      │
│  - 初始化 UnifiedLLMClient                                                  │
│  - 初始化 DataSourceRegistry + CtripSource                                  │
│  - 初始化 SearchService / RecommendationService                             │
└──────────────────────────────────────────────────────────────────────────────┘
               │                         │                          │
               ▼                         ▼                          ▼
     ┌────────────────┐        ┌────────────────┐         ┌────────────────────┐
     │ /api/search    │        │ /api/memory    │         │ /api/recommendations│
     │ api/search.py  │        │ api/memory.py  │         │ api/recommendations │
     └────────────────┘        └────────────────┘         └────────────────────┘
               │                         │                          │
               ▼                         ▼                          ▼
     ┌────────────────┐        ┌────────────────────────┐         ┌────────────────────────┐
     │ SearchService  │        │ RecommendationService  │         │ RecommendationService  │
     └────────────────┘        └────────────────────────┘         └────────────────────────┘
               │                         │
               │                         ├──────────────────────────────┐
               │                         │                              │
               ▼                         ▼                              ▼
     ┌────────────────────┐     ┌────────────────────┐        ┌────────────────────┐
     │ UnifiedLLMClient   │     │ LongTermMemory     │        │  PostgreSQL        │
     │ - parse_intent     │     │ - preferences      │        │  用户偏好/查询/点击 │
     │ - recommendation   │     │ - query history    │        └────────────────────┘
     └────────────────────┘     │ - click history    │
               │                └────────────────────┘
               │
               ▼
     ┌────────────────────┐
     │ DataSourceRegistry │
     └────────────────────┘
               │
               ▼
     ┌────────────────────┐
     │ CtripSource        │
     │ - search_flights   │
     │ - get_history_prices│
     └────────────────────┘
               │
               ▼
     ┌──────────────────────────────┐
     │ 第三方抓取 / flights_monitor │
     │ CtripFlightClient.search...  │
     └──────────────────────────────┘
               │
               ▼
     ┌───────────────────────────────────────────────────────────────┐
     │ 工具层                                                         │
     │ compare_prices / analyze_history / match_preference /         │
     │ generate_signals                                               │
     └───────────────────────────────────────────────────────────────┘
```

说明：

- 当前真正的主搜索链路是：`/api/search → SearchService → LLM + CtripSource + 分析工具`
- 当前真正的记忆链路是：`/api/memory → RecommendationService → LongTermMemory → PostgreSQL`
- Redis、MemoryManager、IntentionAgent、OrchestrationAgent、Skill Registry 已初始化或预留，但暂时没有深度进入主接口调用链
