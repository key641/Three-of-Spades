import { FormEvent, useEffect, useRef, useState, useCallback } from "react";
import { Send, MapPin, Users, Wallet, Pencil, LocateFixed, Clock, Shuffle, ChevronLeft, Copy, RefreshCw, Trash2, ArrowUp, ArrowDown, Navigation, Sun } from "lucide-react";
import { AgentTrace } from "../components/AgentTrace";
import { ChatPanel } from "../components/ChatPanel";
import { RouteCompare } from "../components/RouteCompare";
import { UserProfileBadge } from "../components/UserProfileBadge";
import { MapPanel } from "../components/MapPanel";
import { BottomSheet } from "../components/BottomSheet";
import type { SheetSnap } from "../components/BottomSheet";
import type { OnboardingProfile, TripConstraints } from "../hooks/useOnboarding";
import type { PoiAction } from "../components/RouteTimeline";
import { DEFAULT_TRIP_CONSTRAINTS } from "../hooks/useOnboarding";
import { useChat } from "../hooks/useChat";

// 当前显示哪个 Sheet：对话 or 方案
// ── 路线编辑 Sheet ────────────────────────────────────────────
import type { RouteStop } from "../api/types";

interface RouteEditSheetProps {
  stops: RouteStop[];
  onClose: () => void;
  onSave: (newStops: RouteStop[]) => void;
}

function RouteEditSheet({ stops: initialStops, onClose, onSave }: RouteEditSheetProps) {
  const [stops, setStops] = useState<RouteStop[]>(initialStops);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const hasSelection = selectedIds.size > 0;

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function moveUp(idx: number) {
    if (idx === 0) return;
    setStops((prev) => {
      const next = [...prev];
      [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
      return next;
    });
  }

  function moveDown(idx: number) {
    setStops((prev) => {
      if (idx >= prev.length - 1) return prev;
      const next = [...prev];
      [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
      return next;
    });
  }

  function handleCopy() {
    if (!hasSelection) return;
    setStops((prev) => {
      const next: RouteStop[] = [];
      prev.forEach((stop) => {
        next.push(stop);
        if (selectedIds.has(stop.poi_id)) {
          next.push({ ...stop, poi_id: stop.poi_id + "_copy" });
        }
      });
      return next;
    });
    setSelectedIds(new Set());
  }

  function handleReplace() {
    if (!hasSelection) return;
    // 「替换」：将选中项名称后缀标记（实际场景应弹出搜索）
    // 此处作为 MVP：在名称加 [待替换] 标记，供 AI 识别
    setStops((prev) =>
      prev.map((stop) =>
        selectedIds.has(stop.poi_id)
          ? { ...stop, name: stop.name + "（待替换）" }
          : stop
      )
    );
    setSelectedIds(new Set());
  }

  function handleDelete() {
    if (!hasSelection) return;
    setStops((prev) => prev.filter((s) => !selectedIds.has(s.poi_id)));
    setSelectedIds(new Set());
  }

  // 类别标识（无 emoji）
  function categoryLabel(cat: string): string {
    const m: Record<string, string> = {
      food: "餐饮", restaurant: "餐饮", culture: "文化", museum: "博物馆",
      nature: "自然", park: "公园", shopping: "购物", landmark: "景点",
      show: "演出", rest: "休闲", citywalk: "漫游",
    };
    return m[cat] ?? "地点";
  }

  return (
    <div className="edit-sheet-overlay" onClick={onClose}>
      <div className="edit-sheet" onClick={(e) => e.stopPropagation()}>
        {/* 顶部标题栏 */}
        <div className="edit-sheet-header">
          <div className="edit-sheet-handle" />
          <span className="edit-sheet-title">编辑行程</span>
          <div className="edit-sheet-header-row">
            <span className="edit-sheet-hint">点击圆环选择，拖动箭头排序</span>
            <button type="button" className="edit-sheet-save" onClick={() => onSave(stops)}>
              完成
            </button>
          </div>
        </div>

        {/* POI 列表 */}
        <div className="edit-sheet-list">
          {stops.map((stop, idx) => {
            const selected = selectedIds.has(stop.poi_id);
            return (
              <div key={stop.poi_id} className={`edit-poi-row${selected ? " selected" : ""}`}>
                {/* 选择圆环 */}
                <button
                  type="button"
                  className={`edit-poi-ring${selected ? " active" : ""}`}
                  onClick={() => toggleSelect(stop.poi_id)}
                  aria-label={selected ? "取消选择" : "选择"}
                >
                  {selected && <span className="edit-poi-ring-dot" />}
                </button>

                {/* 序号 + 信息 */}
                <div className="edit-poi-info">
                  <span className="edit-poi-index">{idx + 1}</span>
                  <span className="edit-poi-cat-label">{categoryLabel(stop.category)}</span>
                  <div className="edit-poi-text">
                    <span className="edit-poi-name">{stop.name}</span>
                    <span className="edit-poi-meta">
                      {stop.start_time && `${stop.start_time} · `}
                      {stop.estimated_cost > 0 ? `¥${stop.estimated_cost}` : "免费"}
                    </span>
                  </div>
                </div>

                {/* 上下箭头 */}
                <div className="edit-poi-arrows">
                  <button
                    type="button"
                    className="edit-poi-arrow"
                    onClick={() => moveUp(idx)}
                    disabled={idx === 0}
                    aria-label="上移"
                  >
                    <ArrowUp size={14} />
                  </button>
                  <button
                    type="button"
                    className="edit-poi-arrow"
                    onClick={() => moveDown(idx)}
                    disabled={idx === stops.length - 1}
                    aria-label="下移"
                  >
                    <ArrowDown size={14} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* 底部操作栏 */}
        <div className="edit-sheet-actions">
          <button
            type="button"
            className={`edit-action-btn${hasSelection ? "" : " disabled"}`}
            disabled={!hasSelection}
            onClick={handleCopy}
          >
            <Copy size={16} />
            复制
          </button>
          <button
            type="button"
            className={`edit-action-btn${hasSelection ? "" : " disabled"}`}
            disabled={!hasSelection}
            onClick={handleReplace}
          >
            <RefreshCw size={16} />
            替换
          </button>
          <button
            type="button"
            className={`edit-action-btn edit-action-delete${hasSelection ? "" : " disabled"}`}
            disabled={!hasSelection}
            onClick={handleDelete}
          >
            <Trash2 size={16} />
            删除
          </button>
        </div>
      </div>
    </div>
  );
}

interface PlannerPreset {
  goals?: string[];
  title?: string;
}

interface PlannerPageProps {
  profile: OnboardingProfile;
  onResetProfile: () => void;
  /** 从首页带入的预设参数（主题标签/路线标题） */
  preset?: PlannerPreset | null;
  /** 预设参数消费后回调（避免重复触发） */
  onPresetConsumed?: () => void;
  /** Setup 页面点击返回时，跳回首页 */
  onBackToHome?: () => void;
  /** 行程完结（关闭总结页）时，保存记录并跳回首页 */
  onTripFinished?: (route: import("../api/types").Route, avgScore: number) => void;
}

// ── 常量 ──────────────────────────────────────────────────────
const CITIES = ["北京", "上海", "广州", "深圳", "成都", "杭州", "南京", "武汉", "西安", "重庆", "厦门", "其他"];

// Mock 出发位置（实际可接入 GPS 逆地理编码）
const MOCK_LOCATION = "北京市朝阳区望京";

// 坐标 → 城市名映射（基于大致区域，离线判断，无需额外 API）
const CITY_BOUNDS: { name: string; latMin: number; latMax: number; lngMin: number; lngMax: number }[] = [
  { name: "上海",  latMin: 30.7, latMax: 31.9, lngMin: 120.9, lngMax: 122.0 },
  { name: "北京",  latMin: 39.4, latMax: 41.1, lngMin: 115.4, lngMax: 117.5 },
  { name: "广州",  latMin: 22.5, latMax: 23.9, lngMin: 112.9, lngMax: 114.0 },
  { name: "深圳",  latMin: 22.3, latMax: 22.8, lngMin: 113.7, lngMax: 114.6 },
  { name: "成都",  latMin: 30.0, latMax: 31.3, lngMin: 103.2, lngMax: 104.9 },
  { name: "杭州",  latMin: 29.2, latMax: 30.6, lngMin: 119.1, lngMax: 120.7 },
  { name: "南京",  latMin: 31.2, latMax: 32.6, lngMin: 118.3, lngMax: 119.3 },
  { name: "武汉",  latMin: 29.9, latMax: 31.4, lngMin: 113.7, lngMax: 115.1 },
  { name: "西安",  latMin: 33.4, latMax: 34.6, lngMin: 107.6, lngMax: 109.5 },
  { name: "重庆",  latMin: 28.1, latMax: 32.2, lngMin: 105.3, lngMax: 110.2 },
  { name: "厦门",  latMin: 24.1, latMax: 24.7, lngMin: 117.9, lngMax: 118.4 },
];

function coordsToCity(lat: number, lng: number): string {
  for (const b of CITY_BOUNDS) {
    if (lat >= b.latMin && lat <= b.latMax && lng >= b.lngMin && lng <= b.lngMax) {
      return b.name;
    }
  }
  return "";
}

/** 自动获取城市：GPS → IP → 空字符串（让用户手选） */
async function detectCity(): Promise<string> {
  // 1. 尝试 GPS
  if ("geolocation" in navigator) {
    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) =>
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 })
      );
      const city = coordsToCity(pos.coords.latitude, pos.coords.longitude);
      if (city) return city;
    } catch {
      // GPS 拒绝/超时，继续降级
    }
  }
  // 2. 尝试 IP 定位
  try {
    const res = await fetch("https://ip-api.com/json/?lang=zh-CN&fields=city", { signal: AbortSignal.timeout(4000) });
    const data = await res.json() as { city?: string };
    const ipCity = data.city ?? "";
    // 匹配到已知城市列表
    const matched = CITIES.find((c) => ipCity.includes(c));
    if (matched) return matched;
  } catch {
    // IP 定位失败
  }
  return "";
}

const TODAY_GOAL_OPTIONS: { key: string; label: string }[] = [
  { key: "citywalk",   label: "街头漫游" },
  { key: "foodie",     label: "美食探店" },
  { key: "culture",    label: "文化艺术" },
  { key: "show_event", label: "演出活动" },
  { key: "landmark",   label: "热门景点" },
  { key: "family",     label: "亲子家庭" },
  { key: "nature",     label: "自然放松" },
  { key: "shopping",   label: "逛街购物" },
];

const BUDGET_OPTIONS: { value: number | null; label: string }[] = [
  { value: null, label: "随意" },
  { value: 100,  label: "¥100 内" },
  { value: 200,  label: "¥100~300" },
  { value: 500,  label: "¥300+" },
];

const PEOPLE_OPTIONS: { value: number; label: string }[] = [
  { value: 1, label: "一个人" },
  { value: 2, label: "2人" },
  { value: 3, label: "3人" },
  { value: 4, label: "4人" },
  { value: 5, label: "5人+" },
];

// ── Mock 天气数据 ──────────────────────────────────────────────
const MOCK_WEATHER = {
  city:      "北京市朝阳区",
  condition: "晴",
  tempHigh:  28,
  tempLow:   17,
  wind:      "东南风 3级",
  humidity:  "45%",
  tip:       "适合户外出行，记得防晒",
};

// ── 构建 AI 发起消息 ───────────────────────────────────────────
function buildInitMessage(trip: TripConstraints): string {
  const parts: string[] = [];

  // 出发位置
  parts.push(`我在${trip.location || trip.city}`);

  // 人数
  const peopleMap: Record<number, string> = { 1: "一个人", 2: "两个人", 3: "三个人", 4: "四个人" };
  parts.push(peopleMap[trip.people] ?? `${trip.people}个人`);

  // 时间段
  if (trip.start_time && trip.end_time) {
    parts.push(`从${trip.start_time}到${trip.end_time}`);
  } else if (trip.start_time) {
    parts.push(`从${trip.start_time}出发`);
  } else if (trip.end_time) {
    parts.push(`需要${trip.end_time}前结束`);
  } else {
    const durationMap: Record<number, string> = { 2: "大概2小时", 3: "半天", 5: "大半天", 8: "一整天" };
    parts.push(durationMap[trip.duration] ?? `大概${trip.duration}小时`);
  }

  // 今天想玩什么
  const goalLabels = trip.today_goals
    .map((k) => TODAY_GOAL_OPTIONS.find((o) => o.key === k)?.label)
    .filter(Boolean);
  if (goalLabels.length > 0) {
    parts.push(`想${goalLabels.join("、")}`);
  }

  // 预算
  if (trip.budget_per_person != null) {
    parts.push(`人均预算${trip.budget_per_person}元左右`);
  }

  return parts.join("，") + "，帮我规划一下今天的行程吧！";
}

// ── 智能追问系统（mock 数据） ──────────────────────────────────

interface FollowUpOption { label: string; value: string; }
interface FollowUpQuestion {
  id: string;
  icon: string;
  question: string;
  options: FollowUpOption[];
}

/** 根据 trip 内容生成 1-2 个情境化追问（TripSetupPanel 路径使用） */
function buildFollowUpQuestions(trip: TripConstraints): FollowUpQuestion[] {
  const questions: FollowUpQuestion[] = [];
  const goals = trip.today_goals;
  const hour = trip.start_time ? parseInt(trip.start_time.split(":")[0], 10) : null;

  // 天气 + 自然类场景
  if (goals.includes("nature") || goals.includes("citywalk")) {
    questions.push({
      id: "weather",
      icon: "☀️",
      question: "今日天气晴好，想多接触大自然吗？",
      options: [
        { label: "好呀，多安排户外", value: "prefer_outdoor" },
        { label: "室内外都行",       value: "mixed" },
        { label: "暂时不了",         value: "prefer_indoor" },
      ],
    });
  }

  // 出行高峰期（周末 / 出发时间在 10-13 点）
  const isWeekend = [0, 6].includes(new Date().getDay());
  const isPeakHour = hour !== null && hour >= 10 && hour <= 13;
  if (isWeekend || isPeakHour) {
    questions.push({
      id: "crowd",
      icon: "🚦",
      question: `今天是${isWeekend ? "周末" : "出行高峰期"}，人流较多，建议安排 2-3 个地点，你觉得呢？`,
      options: [
        { label: "好呀，精简一些", value: "compact" },
        { label: "看你安排",       value: "auto" },
        { label: "再多几个吧",     value: "more" },
      ],
    });
  }

  // 美食 + 多人
  if (goals.includes("foodie") && trip.people >= 3) {
    questions.push({
      id: "food_style",
      icon: "🍽️",
      question: `你们 ${trip.people} 个人一起，有口味偏好吗？`,
      options: [
        { label: "本地特色优先",   value: "local" },
        { label: "人气网红店优先", value: "popular" },
        { label: "都可以，随机",   value: "any" },
      ],
    });
  }

  // 演出 / 展览类
  if (goals.includes("show_event")) {
    questions.push({
      id: "show_type",
      icon: "🎭",
      question: "演出 / 活动方面，有偏好吗？",
      options: [
        { label: "音乐演出",   value: "music" },
        { label: "展览 / 展览", value: "exhibition" },
        { label: "都可以",     value: "any" },
      ],
    });
  }

  // 购物 + 预算
  if (goals.includes("shopping")) {
    questions.push({
      id: "shop_style",
      icon: "🛍️",
      question: "逛街购物，更倾向哪种？",
      options: [
        { label: "潮流集合 / 小众品牌", value: "trendy" },
        { label: "大型商场 / 品牌店",   value: "mall" },
        { label: "都行，沿路逛",         value: "casual" },
      ],
    });
  }

  // 默认兜底（没有任何匹配时）
  if (questions.length === 0) {
    questions.push({
      id: "pace",
      icon: "🎯",
      question: "今天出行节奏想要怎样？",
      options: [
        { label: "慢慢来，放松为主", value: "relaxed" },
        { label: "紧凑一些，多转几处", value: "packed" },
        { label: "随缘就好",          value: "auto" },
      ],
    });
  }

  // 最多返回 2 个
  return questions.slice(0, 2);
}

/** 首次自由输入后的通用追问（2-3 个，不依赖 TripConstraints） */
function buildWelcomeFollowUpQuestions(): FollowUpQuestion[] {
  const isWeekend = [0, 6].includes(new Date().getDay());
  return [
    {
      id: "pace",
      icon: "🎯",
      question: "今天的出行节奏想要怎样？",
      options: [
        { label: "悠闲慢游，重在体验", value: "relaxed" },
        { label: "紧凑充实，多逛几处", value: "packed" },
        { label: "随缘就好",            value: "auto" },
      ],
    },
    {
      id: "people",
      icon: "👥",
      question: "和谁一起出行？",
      options: [
        { label: "我一个人",       value: "solo" },
        { label: "两人小约会",     value: "couple" },
        { label: "家人 / 多人团", value: "group" },
      ],
    },
    {
      id: "crowd",
      icon: isWeekend ? "🚦" : "⏰",
      question: isWeekend
        ? "今天是周末，热门景点人流较多，是否避开？"
        : "今天人少，想去热门打卡地还是小众宝藏地？",
      options: isWeekend
        ? [
            { label: "避开人多，偏安静", value: "avoid_crowd" },
            { label: "不介意，热闹也好", value: "ok_crowd" },
            { label: "随便你安排",        value: "auto" },
          ]
        : [
            { label: "热门打卡地",   value: "popular" },
            { label: "小众宝藏地",   value: "hidden" },
            { label: "两者都要",     value: "mixed" },
          ],
    },
  ];
}

/** 将通用追问答案拼成补充说明 */
function buildWelcomeSupplement(answers: Record<string, string>): string {
  const parts: string[] = [];
  const map: Record<string, Record<string, string>> = {
    pace:   { relaxed: "节奏轻松悠闲", packed: "节奏紧凑充实", auto: "节奏随缘" },
    people: { solo: "独自出行", couple: "两人同行", group: "多人出行" },
    crowd:  {
      avoid_crowd: "尽量避开人多的地方",
      ok_crowd:    "不介意人流",
      auto:        "地点类型不限",
      popular:     "偏向热门打卡地",
      hidden:      "偏向小众宝藏地",
      mixed:       "热门与小众兼顾",
    },
  };
  for (const [qid, val] of Object.entries(answers)) {
    const hint = map[qid]?.[val];
    if (hint) parts.push(hint);
  }
  return parts.length > 0 ? "，" + parts.join("，") : "";
}

/** 将 TripSetupPanel 追问答案拼成补充说明 */
function buildFollowUpSupplement(answers: Record<string, string>): string {
  const parts: string[] = [];
  const map: Record<string, Record<string, string>> = {
    weather:    { prefer_outdoor: "尽量安排户外场景", mixed: "室内外均可", prefer_indoor: "偏向室内场景" },
    crowd:      { compact: "地点精简 2-3 个即可", auto: "地点数量你来定", more: "可以多安排几个地点" },
    food_style: { local: "美食偏向本地特色", popular: "美食偏向人气网红店", any: "美食随机推荐" },
    show_type:  { music: "活动偏向音乐演出", exhibition: "活动偏向展览", any: "活动类型不限" },
    shop_style: { trendy: "购物偏向潮流小众", mall: "购物偏向大型商场", casual: "购物随缘逛" },
    pace:       { relaxed: "节奏轻松慢游", packed: "节奏紧凑多转", auto: "节奏随缘" },
  };
  for (const [qid, val] of Object.entries(answers)) {
    const hint = map[qid]?.[val];
    if (hint) parts.push(hint);
  }
  return parts.length > 0 ? "，" + parts.join("，") : "";
}

// ── 智能追问卡片组件（全题同时展示 + 思考动效）─────────────────
interface SmartFollowUpProps {
  questions: FollowUpQuestion[];
  /** 所有问题都被回答后触发，答案作为参数传出 */
  onAllAnswered: (answers: Record<string, string>) => void;
  /** 是否锁定为只读（AI 已开始响应后禁止修改） */
  readonly?: boolean;
}

function SmartFollowUp({ questions, onAllAnswered, readonly = false }: SmartFollowUpProps) {
  const [answers, setAnswers]       = useState<Record<string, string>>({});
  const [showQuestions, setShowQuestions] = useState(false); // 先显示 thinking，延迟后再显示卡片
  const sentRef = useRef(false); // 保证 onAllAnswered 只触发一次

  // 首次渲染：短暂 thinking 后展示追问卡片
  // TODO: 后续追问内容应由真实接口返回，thinking 时长应对应实际请求耗时，而非固定值
  useEffect(() => {
    const t = setTimeout(() => setShowQuestions(true), 1200);
    return () => clearTimeout(t);
  }, []);

  function handleSelect(qid: string, value: string) {
    if (readonly) return;
    const newAnswers = { ...answers, [qid]: value };
    setAnswers(newAnswers);
    // 全部回答完毕 → 触发一次 onAllAnswered，之后不再重复
    if (!sentRef.current && questions.every((q) => newAnswers[q.id] !== undefined)) {
      sentRef.current = true;
      onAllAnswered(newAnswers);
    }
  }

  return (
    <div className="followup-steps">
      {/* 思考中气泡 */}
      {!showQuestions && (
        <div className="bubble bubble-assistant typing-dots followup-thinking">
          <span /><span /><span />
        </div>
      )}

      {/* 追问卡片（thinking 结束后淡入，选完后变只读保留展示） */}
      {showQuestions && questions.map((q) => (
        <div key={q.id} className={`followup-card${readonly ? " followup-card--done" : ""}`}>
          <div className="followup-header">
            <span className="followup-title">{q.question}</span>
          </div>
          <div className="followup-options">
            {q.options.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`followup-opt${answers[q.id] === opt.value ? " selected" : ""}${readonly && answers[q.id] !== opt.value ? " followup-opt--faded" : ""}`}
                onClick={() => handleSelect(q.id, opt.value)}
                disabled={readonly}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── 规划欢迎首屏 ──────────────────────────────────────────────
interface PlanningWelcomeScreenProps {
  onSend: (text: string) => void;
  onBack: () => void;
}

function PlanningWelcomeScreen({ onSend, onBack }: PlanningWelcomeScreenProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const SUGGESTIONS = [
    "今天想来一场 citywalk",
    "帮我找附近好吃的",
    "今天想去打卡网红景点",
  ];

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const msg = text.trim();
    if (!msg) return;
    onSend(msg);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as FormEvent);
    }
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setText(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }

  // 自动聚焦输入框
  useEffect(() => {
    setTimeout(() => textareaRef.current?.focus(), 300);
  }, []);

  return (
    <div className="plan-welcome">
      {/* 顶部退出 */}
      <button type="button" className="plan-welcome-back" onClick={onBack}>
        <ChevronLeft size={18} />
        <span>退出</span>
      </button>

      {/* 主体内容 */}
      <div className="plan-welcome-body">
        {/* 标语 */}
        <div className="plan-welcome-hero">
          <Navigation size={36} strokeWidth={1.5} className="plan-welcome-icon" />
          <h1 className="plan-welcome-title">今天想去哪儿？</h1>
          <p className="plan-welcome-sub">告诉 AI 你的想法，立刻生成专属行程</p>
        </div>

        {/* 定位 + 天气信息条 */}
        <div className="plan-welcome-info">
          <div className="plan-welcome-info-item">
            <LocateFixed size={13} />
            <span>{MOCK_LOCATION}</span>
          </div>
          <div className="plan-welcome-info-divider" />
          <div className="plan-welcome-info-item">
            <Sun size={13} />
            <span>{MOCK_WEATHER.condition} {MOCK_WEATHER.tempHigh}°/{MOCK_WEATHER.tempLow}°</span>
          </div>
          <div className="plan-welcome-info-divider" />
          <div className="plan-welcome-info-item plan-welcome-info-tip">
            <span>{MOCK_WEATHER.tip}</span>
          </div>
        </div>

        {/* 输入框 */}
        <form className="plan-welcome-form" onSubmit={handleSubmit}>
          <div className="plan-welcome-input-wrap">
            <textarea
              ref={textareaRef}
              className="plan-welcome-textarea"
              value={text}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder="随便说说，比如「朝阳区半天 citywalk，预算100」…"
              rows={2}
              aria-label="输入出行想法"
            />
            <button
              type="submit"
              className="plan-welcome-send"
              disabled={!text.trim()}
              aria-label="发送"
            >
              <Send size={18} />
            </button>
          </div>
        </form>

        {/* 快捷建议气泡 */}
        <div className="plan-welcome-suggestions">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              className="plan-welcome-sug"
              onClick={() => { setText(s); textareaRef.current?.focus(); }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── 本次行程设置面板（欢迎引导） ───────────────────────────────
interface TripSetupPanelProps {
  profile: OnboardingProfile;
  onStart: (trip: TripConstraints) => void;
  onSkip: () => void;
  /** 首页预设的标签（点击主题/路线跳转过来时携带） */
  presetGoals?: string[];
}

function TripSetupPanel({ profile, onStart, onSkip, presetGoals }: TripSetupPanelProps) {
  const [trip, setTrip] = useState<TripConstraints>(() => {
    // 优先使用预设目标，其次从 profile.scenarios 取
    const goals = presetGoals?.length
      ? presetGoals.filter((s) => TODAY_GOAL_OPTIONS.some((o) => o.key === s))
      : profile.scenarios.filter((s) => TODAY_GOAL_OPTIONS.some((o) => o.key === s)).slice(0, 2);
    return { ...DEFAULT_TRIP_CONSTRAINTS, today_goals: goals };
  });
  const [locating, setLocating] = useState(true);       // 定位中
  const [locateResult, setLocateResult] = useState<"ok" | "manual" | "pending">("pending");
  const [cityExpanded, setCityExpanded] = useState(false); // 是否展开手选
  const [customGoal, setCustomGoal] = useState("");      // 自定义玩法输入

  function set<K extends keyof TripConstraints>(key: K, value: TripConstraints[K]) {
    setTrip((prev) => ({ ...prev, [key]: value }));
  }

  function toggleGoal(key: string) {
    setTrip((prev) => ({
      ...prev,
      today_goals: prev.today_goals.includes(key)
        ? prev.today_goals.filter((k) => k !== key)
        : [...prev.today_goals, key],
    }));
  }

  // 组件挂载后自动定位（mock 出发位置）
  useEffect(() => {
    setLocating(true);
    set("location", MOCK_LOCATION);
    set("city", "北京");
    detectCity().then((city) => {
      setLocating(false);
      if (city) {
        set("city", city);
      }
      setLocateResult("ok");
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="setup-page">
      {/* 顶部导航栏 */}
      <div className="setup-page-nav">
        <button
          type="button"
          className="setup-page-back"
          onClick={onSkip}
          aria-label="返回"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <span className="setup-page-nav-title">创建今日行程</span>
        <div style={{ width: 36 }} />
      </div>

      <div className="setup-panel">
        {/* 标题 */}
        <div className="setup-header">
          <Navigation size={28} strokeWidth={1.5} className="setup-emoji" />
          <h2 className="setup-title">今天想去哪儿玩？</h2>
          <p className="setup-subtitle">告诉我这次的安排，AI 直接给你出方案</p>
        </div>

        <div className="setup-fields">
          {/* 出发位置 — mock 数据 + 用户自由输入 */}
          <div className="setup-field">
            <div className="setup-field-label"><MapPin size={13} /> 出发位置</div>
            <div className="setup-city-status">
              {locating ? (
                <span className="setup-locate-tag locating">
                  <LocateFixed size={13} className="locate-spin" /> 定位中…
                </span>
              ) : !cityExpanded ? (
                <>
                  <span className="setup-locate-tag located">
                    <LocateFixed size={13} /> {trip.location || trip.city}
                  </span>
                  <button
                    type="button"
                    className="setup-city-toggle"
                    onClick={() => setCityExpanded(true)}
                  >
                    更改出发位置
                  </button>
                </>
              ) : (
                <div className="setup-location-input-row">
                  <input
                    type="text"
                    className="setup-custom-goal-input"
                    placeholder="输入出发位置，如：上海市静安区南京西路"
                    defaultValue={trip.location || trip.city}
                    autoFocus
                    onBlur={(e) => {
                      const val = e.target.value.trim();
                      if (val) { set("location", val); }
                      setCityExpanded(false);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        const val = (e.target as HTMLInputElement).value.trim();
                        if (val) { set("location", val); }
                        setCityExpanded(false);
                      }
                      if (e.key === "Escape") { setCityExpanded(false); }
                    }}
                  />
                </div>
              )}
            </div>
          </div>

          {/* 人数 */}
          <div className="setup-field">
            <div className="setup-field-label"><Users size={13} /> 几个人</div>
            <div className="setup-tags">
              {PEOPLE_OPTIONS.map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  className={`setup-tag${trip.people === value ? " active" : ""}`}
                  onClick={() => set("people", value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* 出发 / 结束时间 */}
          <div className="setup-field">
            <div className="setup-field-label"><Clock size={13} /> 出行时间 <span className="setup-optional">可不填</span></div>
            <div className="setup-time-row">
              <label className="setup-time-label">出发</label>
              <input
                type="time"
                className="setup-time-input"
                value={trip.start_time}
                onChange={(e) => set("start_time", e.target.value)}
              />
              <span className="setup-time-sep">—</span>
              <label className="setup-time-label">结束</label>
              <input
                type="time"
                className="setup-time-input"
                value={trip.end_time}
                onChange={(e) => set("end_time", e.target.value)}
              />
              {(trip.start_time || trip.end_time) && (
                <button
                  type="button"
                  className="setup-time-clear"
                  onClick={() => { set("start_time", ""); set("end_time", ""); }}
                >
                  清空
                </button>
              )}
            </div>
          </div>

          {/* 今天想玩什么 */}
          <div className="setup-field">
            <div className="setup-field-label"><MapPin size={13} /> 今天想玩什么 <span className="setup-optional">可多选，可跳过</span></div>
            <div className="setup-tags">
              {TODAY_GOAL_OPTIONS.map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  className={`setup-tag${trip.today_goals.includes(key) ? " active" : ""}`}
                  onClick={() => toggleGoal(key)}
                >
                  {label}
                </button>
              ))}
              {/* 随机推荐 */}
              <button
                type="button"
                className={`setup-tag setup-tag--random${trip.today_goals.includes("__random__") ? " active" : ""}`}
                onClick={() => {
                  setTrip((prev) => ({
                    ...prev,
                    today_goals: prev.today_goals.includes("__random__") ? [] : ["__random__"],
                  }));
                }}
              >
                <Shuffle size={12} /> 随机推荐
              </button>
            </div>
            {/* 自定义输入 */}
            <div className="setup-custom-goal-row">
              <input
                type="text"
                className="setup-custom-goal-input"
                placeholder="自定义，比如：找个安静的书店…"
                value={customGoal}
                maxLength={30}
                onChange={(e) => setCustomGoal(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && customGoal.trim()) {
                    e.preventDefault();
                    const val = customGoal.trim();
                    if (!trip.today_goals.includes(val)) {
                      setTrip((prev) => ({ ...prev, today_goals: [...prev.today_goals.filter(k => k !== "__random__"), val] }));
                    }
                    setCustomGoal("");
                  }
                }}
              />
              {customGoal.trim() && (
                <button
                  type="button"
                  className="setup-custom-goal-add"
                  onClick={() => {
                    const val = customGoal.trim();
                    if (!trip.today_goals.includes(val)) {
                      setTrip((prev) => ({ ...prev, today_goals: [...prev.today_goals.filter(k => k !== "__random__"), val] }));
                    }
                    setCustomGoal("");
                  }}
                >
                  + 添加
                </button>
              )}
            </div>
            {/* 已添加的自定义标签 */}
            {trip.today_goals.filter(k => !TODAY_GOAL_OPTIONS.some(o => o.key === k) && k !== "__random__").length > 0 && (
              <div className="setup-tags" style={{ marginTop: 6 }}>
                {trip.today_goals
                  .filter(k => !TODAY_GOAL_OPTIONS.some(o => o.key === k) && k !== "__random__")
                  .map(k => (
                    <button
                      key={k}
                      type="button"
                      className="setup-tag active"
                      onClick={() => setTrip((prev) => ({ ...prev, today_goals: prev.today_goals.filter(g => g !== k) }))}
                    >
                      {k} ×
                    </button>
                  ))}
              </div>
            )}
          </div>

          {/* 人均预算 */}
          <div className="setup-field">
            <div className="setup-field-label"><Wallet size={13} /> 人均预算</div>
            <div className="setup-tags">
              {BUDGET_OPTIONS.map(({ value, label }) => (
                <button
                  key={String(value)}
                  type="button"
                  className={`setup-tag${trip.budget_per_person === value ? " active" : ""}`}
                  onClick={() => set("budget_per_person", value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 底部操作 */}
        <div className="setup-footer">
          <button
            type="button"
            className="setup-btn-start"
            onClick={() => onStart(trip)}
          >
            开始规划 →
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 顶部轻量条件胶囊栏 ────────────────────────────────────────
interface TripPillBarProps {
  trip: TripConstraints;
  onEdit: () => void;
}

function TripPillBar({ trip, onEdit }: TripPillBarProps) {
  const goalLabels = trip.today_goals
    .map((k) => TODAY_GOAL_OPTIONS.find((o) => o.key === k)?.label)
    .filter(Boolean)
    .join(" · ");

  const pills = [
    trip.city,
    `${trip.people}人`,
    trip.duration === 3 ? "半天" : trip.duration === 8 ? "一天" : `${trip.duration}h`,
    trip.budget_per_person != null ? `¥${trip.budget_per_person}` : null,
    goalLabels || null,
  ].filter(Boolean) as string[];

  return (
    <div className="pill-bar">
      <div className="pill-bar-pills">
        {pills.map((p) => (
          <span key={p} className="pill">{p}</span>
        ))}
      </div>
      <button type="button" className="pill-bar-edit" onClick={onEdit} title="修改本次条件">
        <Pencil size={13} />
        <span>改一改</span>
      </button>
    </div>
  );
}

// ── 根据场景和偏好构建 ReplanPanel 的事件提示文本 ─────────────
function buildReplanMessage(eventKey: string, currentRouteId?: string): string {
  const routeHint = currentRouteId ? `（当前路线 ${currentRouteId}）` : "";
  const map: Record<string, string> = {
    queue90: `餐厅排队 90 分钟${routeHint}，帮我换一个等待时间短的替代方案`,
    traffic: `路上堵车了${routeHint}，帮我调整后续行程`,
    tired:   `我们有点累了${routeHint}，帮我缩短行程或推荐就近休息的地方`,
  };
  return map[eventKey] ?? `发生了突发情况${routeHint}，请帮我重新规划`;
}

function buildActionMessage(actionKey: string, routeId: string): string {
  const map: Record<string, string> = {
    budget: `对路线 ${routeId} 重新规划，降低人均消费`,
    queue:  `对路线 ${routeId} 重新规划，避开需要排队的地点`,
    family: `对路线 ${routeId} 加入亲子友好筛选条件`,
    talk:   ``, // "跟 AI 说" 由用户在输入框自由填写，不预设消息
  };
  return map[actionKey] ?? `请优化路线 ${routeId}`;
}

/** 将 POI 级操作转成 AI 消息文本（或返回 null 表示仅填输入框） */
function buildPoiActionMessage(action: PoiAction, routeId: string): string | null {
  switch (action.type) {
    case "swap_same":
      return `路线 ${routeId} 中的「${action.poiName}」我不满意，帮我换一个同类型的地点`;
    case "swap_as":
      return `路线 ${routeId} 中的「${action.poiName}」帮我换成${action.category}类型的地点`;
    case "remove":
      return `路线 ${routeId} 中去掉「${action.poiName}」，帮我重新衔接路线`;
    case "talk_ai":
      // 预填输入框，让用户自己发送
      return null;
  }
}

// ── 主页面 ────────────────────────────────────────────────────
export function PlannerPage({ profile, onResetProfile, preset, onPresetConsumed, onBackToHome, onTripFinished }: PlannerPageProps) {
  const { messages, response, liveTrace, loading, error, send, inject, reset } = useChat();
  const [inputText, setInputText] = useState("");
  const [localProfile, setLocalProfile] = useState<OnboardingProfile>(profile);
  const [trip, setTrip] = useState<TripConstraints | null>(null); // null = 未完成 setup
  const [showSetup, setShowSetup] = useState(true); // 首次进入显示引导面板

  

  // 追问状态：null = 不显示，有值 = 显示追问卡片
  const [followUp, setFollowUp] = useState<{ trip: TripConstraints; questions: FollowUpQuestion[] } | null>(null);
  // 欢迎首屏追问状态：存储首次发送的原始消息 + 通用追问（选完后保留展示，由 done 控制只读）
  const [welcomeFollowUp, setWelcomeFollowUp] = useState<{ pendingMsg: string; questions: FollowUpQuestion[] } | null>(null);
  const [welcomeFollowUpDone, setWelcomeFollowUpDone] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // ── Sheet 状态 ──────────────────────────────────────────────
  const [sheetSnap, setSheetSnap]     = useState<SheetSnap>("half");
  const [activePoi, setActivePoi]     = useState<string | null>(null);
  const [activeRouteIndex, setActiveRouteIndex] = useState(0);

  // ── 编辑 Sheet 状态 ──────────────────────────────────────────
  const [showEditSheet, setShowEditSheet] = useState(false);
  // 当前正在编辑的路线 index（默认编辑第一条）
  const [editRouteIndex, setEditRouteIndex] = useState(0);
  // 本地可编辑的路线副本（AI 返回后同步，编辑后保存在这里）
  const [editableRoutes, setEditableRoutes] = useState<import("../api/types").Route[]>([]);

  // ── 消费来自首页的预设参数 ──────────────────────────────────
  useEffect(() => {
    if (!preset) return;
    setShowSetup(true);
    setTrip(null);
    setFollowUp(null);
    onPresetConsumed?.();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset]);

  function handleStart(newTrip: TripConstraints) {
    setTrip(newTrip);
    setShowSetup(false);
    setSheetSnap("half");
    const initMsg = buildInitMessage(newTrip);
    inject("user", initMsg);
    const questions = buildFollowUpQuestions(newTrip);
    setFollowUp({ trip: newTrip, questions });
  }

  function handleFollowUpConfirm(answers: Record<string, string>) {
    if (!followUp) return;
    const supplement = buildFollowUpSupplement(answers);
    const finalMsg = buildInitMessage(followUp.trip).replace("，帮我规划一下今天的行程吧！", supplement + "，帮我规划一下今天的行程吧！");
    setFollowUp(null);
    send(finalMsg, localProfile, followUp.trip);
  }

  function handleWelcomeFollowUpConfirm(answers: Record<string, string>) {
    if (!welcomeFollowUp) return;
    const supplement = buildWelcomeSupplement(answers);
    const finalMsg = welcomeFollowUp.pendingMsg + supplement;
    // 卡片保留（不 setWelcomeFollowUp(null)），切换为只读态
    setWelcomeFollowUpDone(true);
    // silent=true：不往消息列表插入 user bubble（页面上追问卡片已展示用户选择，无需重复）
    send(finalMsg, localProfile, DEFAULT_TRIP_CONSTRAINTS, true);
  }

  function handleSkip() {
    // Setup 页返回键一律回首页
    onBackToHome?.();
  }

  function handleReEdit() {
    setShowSetup(true);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const msg = inputText.trim();
    if (!msg || loading) return;
    send(msg, localProfile, trip ?? DEFAULT_TRIP_CONSTRAINTS);
    setInputText("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as FormEvent);
    }
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInputText(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }

  function handleReplan(eventKey: string) {
    const currentRouteId = response?.routes?.[0]?.route_id;
    send(buildReplanMessage(eventKey, currentRouteId), localProfile, trip ?? DEFAULT_TRIP_CONSTRAINTS);
  }

  function handleAction(actionKey: string, routeId: string) {
    // 竖向时间轴：「从这里修改行程」——预填输入框
    if (actionKey.startsWith("replan_from:")) {
      const hint = actionKey.slice("replan_from:".length);
      setInputText(hint);
      setTimeout(() => {
        const el = textareaRef.current;
        if (el) {
          el.focus();
          el.setSelectionRange(hint.length, hint.length);
          el.style.height = "auto";
          el.style.height = Math.min(el.scrollHeight, 120) + "px";
        }
      }, 50);
      return;
    }
    // 竖向时间轴：跳过某站——直接发送 AI 消息
    if (actionKey.startsWith("skip_poi:")) {
      const parts = actionKey.split(":");   // ["skip_poi", poiId, poiName]
      const poiName = parts[2] ?? "";
      const msg = `路线 ${routeId} 中跳过「${poiName}」，帮我衔接前后行程`;
      send(msg, localProfile, trip ?? DEFAULT_TRIP_CONSTRAINTS);
      return;
    }
    if (actionKey === "talk") {
      textareaRef.current?.focus();
      return;
    }
    const msg = buildActionMessage(actionKey, routeId);
    if (!msg) return;
    if (actionKey === "swap") {
      send(msg, localProfile, trip ?? DEFAULT_TRIP_CONSTRAINTS, false, {
        event_type: "replace_poi",
        selected_route_id: routeId,
        event_payload: { force_replace: true },
      });
      return;
    }
    send(msg, localProfile, trip ?? DEFAULT_TRIP_CONSTRAINTS);
  }

  const handlePoiAction = useCallback((action: PoiAction, routeId: string) => {
    if (action.type === "talk_ai") {
      // 预填输入框提示，聚焦让用户补充
      const hint = `路线 ${routeId} 中的「${action.poiName}」`;
      setInputText(hint);
      setTimeout(() => {
        const el = textareaRef.current;
        if (el) {
          el.focus();
          el.setSelectionRange(hint.length, hint.length);
          el.style.height = "auto";
          el.style.height = Math.min(el.scrollHeight, 120) + "px";
        }
      }, 50);
      return;
    }
    const msg = buildPoiActionMessage(action, routeId);
    if (msg) send(msg, localProfile, trip ?? DEFAULT_TRIP_CONSTRAINTS);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localProfile, trip]);

  // 地图 POI 被点击 → 高亮
  function handlePoiClick(poiId: string) {
    setActivePoi(poiId);
    if (sheetSnap === "peek") setSheetSnap("half");
  }

  // AI 返回方案后 → 同步可编辑路线副本
  useEffect(() => {
    if ((response?.routes?.length ?? 0) > 0 && !loading) {
      setActiveRouteIndex(0);
      setSheetSnap("half");
      setEditableRoutes(response!.routes.map((r) => ({ ...r, stops: [...r.stops] })));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [response?.routes?.length, loading]);

  function handleResetProfile() {
    reset();
    onResetProfile();
  }

  const hasRoutes = (response?.routes?.length ?? 0) > 0;
  const displayProfile: { preferences?: string[]; avoid_tags?: string[] } =
    response?.user_profile ?? {
      preferences: localProfile.preferences,
      avoid_tags:  localProfile.avoid_tags,
    };

  const currentCity = trip?.city ?? DEFAULT_TRIP_CONSTRAINTS.city;

  // ── 单一 BottomSheet 内容 ──────────────────────────────────
  const sheetContent = (
    <div className="sheet-chat-inner">
      {/* 可滚动内容区 */}
      <div className="sheet-chat-scroll">
        {/* 对话消息列表（追问卡片嵌入第一条 user 消息之后） */}
        <ChatPanel
          messages={messages}
          loading={loading}
          error={error}
          clarifyingQuestion={response?.need_clarification ? (response.clarifying_question ?? null) : null}
          onClarify={(answer) => send(answer, localProfile, trip ?? DEFAULT_TRIP_CONSTRAINTS)}
          afterFirstUserMessage={
            // 欢迎首屏追问（选完后只读保留）
            welcomeFollowUp ? (
              <SmartFollowUp
                questions={welcomeFollowUp.questions}
                onAllAnswered={handleWelcomeFollowUpConfirm}
                readonly={welcomeFollowUpDone}
              />
            ) :
            // TripSetupPanel 路径追问
            (followUp && !loading) ? (
              <SmartFollowUp
                questions={followUp.questions}
                onAllAnswered={handleFollowUpConfirm}
              />
            ) : undefined
          }
        />

        <AgentTrace steps={response?.agent_trace ?? []} loading={loading} />

        {/* 路线方案（有结果时内联展示） */}
        {(hasRoutes || loading) && (
          <div className="sheet-inline-routes">
            <RouteCompare
              routes={response?.routes ?? []}
              loading={loading}
              onAction={handleAction}
              onPoiAction={handlePoiAction}
              onTripFinished={onTripFinished}
              onInjectChat={(text) => {
                setInputText(text);
                setTimeout(() => {
                  const el = textareaRef.current;
                  if (el) {
                    el.focus();
                    el.setSelectionRange(text.length, text.length);
                    el.style.height = "auto";
                    el.style.height = Math.min(el.scrollHeight, 120) + "px";
                  }
                }, 50);
              }}
            />
          </div>
        )}
      </div>

      {/* 输入栏固定在底部 */}
      <form className="sheet-input-bar" onSubmit={handleSubmit}>
        <textarea
          ref={textareaRef}
          value={inputText}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={`告诉我你想怎么玩，例如「${currentCity}半天 citywalk」…`}
          rows={1}
          disabled={loading || showSetup}
          aria-label="输入出行需求"
        />
        <button
          type="submit"
          className="send-btn"
          disabled={loading || !inputText.trim() || showSetup}
          title="发送"
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  );

  return (
    <div className="map-shell">
      {/* ── 地图全屏背景层 ── */}
      <div className="map-bg">
        <MapPanel
          routes={response?.routes ?? []}
          activeRouteIndex={activeRouteIndex}
          activePoi={activePoi}
          onPoiClick={handlePoiClick}
        />
      </div>

      {/* ── 顶部浮动状态栏 ── */}
      <header className="map-topbar">
        <div className="map-topbar-left">
          {!showSetup && (
            <button
              type="button"
              className="map-topbar-back"
              onClick={() => onBackToHome?.()}
              aria-label="退出规划"
            >
              <ChevronLeft size={18} />
              <span>退出</span>
            </button>
          )}
          <Navigation size={18} strokeWidth={2} className="map-topbar-logo" />
          <span className="map-topbar-title">Drifto</span>
        </div>
        <UserProfileBadge
          profile={displayProfile}
          onReset={handleResetProfile}
        />
      </header>

      {/* ── 天气条（顶部导航栏正下方，悬浮在地图上） ── */}
      <div className="map-weather-bar">
        <Sun size={13} className="map-weather-icon" />
        <span className="map-weather-main">{MOCK_WEATHER.condition} {MOCK_WEATHER.tempHigh}°/{MOCK_WEATHER.tempLow}°</span>
        <span className="map-weather-sep">·</span>
        <span className="map-weather-detail">{MOCK_WEATHER.wind}</span>
        <span className="map-weather-sep">·</span>
        <span className="map-weather-tip">{MOCK_WEATHER.tip}</span>
      </div>

      {/* ── 规划欢迎首屏 ── */}
      {showSetup && (
        <PlanningWelcomeScreen
          onBack={handleSkip}
          onSend={(msg) => {
            // 先存消息 + 展示追问，不立刻发 AI
            setShowSetup(false);
            setSheetSnap("half");
            inject("user", msg);
            setWelcomeFollowUp({ pendingMsg: msg, questions: buildWelcomeFollowUpQuestions() });
          }}
        />
      )}

      {/* ── 单一 Sheet ── */}
      {!showSetup && (
        <BottomSheet
          snap={sheetSnap}
          onSnapChange={setSheetSnap}
        >
          {sheetContent}
        </BottomSheet>
      )}

      {/* ── 编辑方案 Sheet（覆盖层） ── */}
      {showEditSheet && editableRoutes.length > 0 && (
        <RouteEditSheet
          stops={editableRoutes[editRouteIndex]?.stops ?? []}
          onClose={() => setShowEditSheet(false)}
          onSave={(newStops) => {
            setEditableRoutes((prev) =>
              prev.map((r, i) =>
                i === editRouteIndex ? { ...r, stops: newStops } : r
              )
            );
            setShowEditSheet(false);
          }}
        />
      )}
    </div>
  );
}
