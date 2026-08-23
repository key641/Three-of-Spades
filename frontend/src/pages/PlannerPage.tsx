import React, { FormEvent, useEffect, useLayoutEffect, useRef, useState, useCallback } from "react";
import { API_BASE_URL } from "../api/client";
import { Send, MapPin, Users, Wallet, Pencil, LocateFixed, Clock, Shuffle, ChevronLeft, Copy, RefreshCw, Trash2, ArrowUp, ArrowDown, Navigation, Sun, X, MessageSquare, Rocket, Menu, Plus } from "lucide-react";
import { AgentTrace } from "../components/AgentTrace";
import { ChatPanel } from "../components/ChatPanel";
import { RouteCompare } from "../components/RouteCompare";
import { MapPanel } from "../components/MapPanel";
import type { RouteStop, Route } from "../api/types";
import type { ChatSessionSnapshot } from "../hooks/useChat";
import type { OnboardingProfile, TripConstraints } from "../hooks/useOnboarding";
import type { PoiAction } from "../components/RouteTimeline";
import { DEFAULT_TRIP_CONSTRAINTS } from "../hooks/useOnboarding";
import { useChat } from "../hooks/useChat";
import { setGpsCache } from "../utils/gpsCache";

// ── 路线编辑 Sheet ────────────────────────────────────────────
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

        <div className="edit-sheet-list">
          {stops.map((stop, idx) => {
            const selected = selectedIds.has(stop.poi_id);
            return (
              <div key={stop.poi_id} className={`edit-poi-row${selected ? " selected" : ""}`}>
                <button
                  type="button"
                  className={`edit-poi-ring${selected ? " active" : ""}`}
                  onClick={() => toggleSelect(stop.poi_id)}
                  aria-label={selected ? "取消选择" : "选择"}
                >
                  {selected && <span className="edit-poi-ring-dot" />}
                </button>

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

// ── 预设 & 类型 ────────────────────────────────────────────────
interface PlannerPreset {
  goals?: string[];
  title?: string;
  initialMsg?: string;
  /** 从侧边栏点击行程进入时为 true，方案就绪后直接跳转看板视图 */
  directBoard?: boolean;
  /** 历史行程的已完成对话快照。 */
  conversation?: ChatSessionSnapshot;
  /** 历史记录选择的精确路线 ID。 */
  routeId?: string;
}

interface PlannerPageProps {
  profile: OnboardingProfile;
  onResetProfile: () => void;
  preset?: PlannerPreset | null;
  onPresetConsumed?: () => void;
  onBackToHome?: () => void;
  onTripFinished?: (route: Route, avgScore: number, conversation?: ChatSessionSnapshot) => void;
  /** 新建行程：保存当前会话（如有）并重置 */
  onNewTrip?: () => void;
  /** 将进行中的路线状态同步至应用层，供首页持续展示 */
  onActiveTripChange?: (route: Route | null) => void;
  /** 应用层保存的进行中路线，用于从首页恢复行程看板 */
  activeTrip?: Route | null;
  /** 仅保存路线到历史（不跳首页） */
  onSaveTrip?: (route: Route, conversation?: ChatSessionSnapshot) => void;
  initialMsg?: string;
  onOpenSidebar?: () => void;
  /** 注册 send 函数给 App 层全局输入栏使用 */
  onSendReady?: (sendFn: (msg: string) => void) => void;
  /** 注入文字到全局输入栏并聚焦 */
  onInjectText?: (text: string) => void;
  /** 上报输入栏禁用状态变化（loading/showSetup） */
  onDisabledChange?: (disabled: boolean) => void;
  /** 上报视图模式变化（board/chat），用于控制全局输入栏显隐 */
  onViewModeChange?: (mode: PlannerViewMode) => void;
}

// ── 视图模式 ──────────────────────────────────────────────────
type PlannerViewMode = "chat" | "board";

// ── 常量 ──────────────────────────────────────────────────────
const CITIES = ["北京", "上海", "广州", "深圳", "成都", "杭州", "南京", "武汉", "西安", "重庆", "厦门", "其他"];
const MOCK_LOCATION = "北京市朝阳区望京";

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

async function detectCity(): Promise<string> {
  if ("geolocation" in navigator) {
    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) =>
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 })
      );
      setGpsCache(pos.coords.latitude, pos.coords.longitude);
      const city = coordsToCity(pos.coords.latitude, pos.coords.longitude);
      if (city) return city;
    } catch {}
  }
  try {
    const res = await fetch("https://ip-api.com/json/?lang=zh-CN&fields=city", { signal: AbortSignal.timeout(4000) });
    const data = await res.json() as { city?: string };
    const ipCity = data.city ?? "";
    const matched = CITIES.find((c) => ipCity.includes(c));
    if (matched) return matched;
  } catch {}
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

const MOCK_WEATHER = {
  city:      "北京市朝阳区",
  condition: "晴",
  tempHigh:  28,
  tempLow:   17,
  wind:      "东南风 3级",
  humidity:  "45%",
  tip:       "适合户外出行，记得防晒",
};

function buildInitMessage(trip: TripConstraints): string {
  const parts: string[] = [];
  parts.push(`我在${trip.location || trip.city}`);
  const peopleMap: Record<number, string> = { 1: "一个人", 2: "两个人", 3: "三个人", 4: "四个人" };
  parts.push(peopleMap[trip.people] ?? `${trip.people}个人`);

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

  const goalLabels = trip.today_goals
    .map((k) => TODAY_GOAL_OPTIONS.find((o) => o.key === k)?.label)
    .filter(Boolean);
  if (goalLabels.length > 0) {
    parts.push(`想${goalLabels.join("、")}`);
  }
  if (trip.budget_per_person != null) {
    parts.push(`人均预算${trip.budget_per_person}元左右`);
  }
  return parts.join("，") + "，帮我规划一下今天的行程吧！";
}

// ── 追问系统 ──────────────────────────────────────────────────
interface FollowUpOption { label: string; value: string; }
interface FollowUpQuestion {
  id: string;
  icon: string;
  question: string;
  options: FollowUpOption[];
}

function buildFollowUpQuestions(trip: TripConstraints): FollowUpQuestion[] {
  const questions: FollowUpQuestion[] = [];
  const goals = trip.today_goals;
  const hour = trip.start_time ? parseInt(trip.start_time.split(":")[0], 10) : null;

  if (goals.includes("nature") || goals.includes("citywalk")) {
    questions.push({
      id: "weather", icon: "☀️",
      question: "今日天气晴好，想多接触大自然吗？",
      options: [
        { label: "好呀，多安排户外", value: "prefer_outdoor" },
        { label: "室内外都行", value: "mixed" },
        { label: "暂时不了", value: "prefer_indoor" },
      ],
    });
  }

  const isWeekend = [0, 6].includes(new Date().getDay());
  const isPeakHour = hour !== null && hour >= 10 && hour <= 13;
  if (isWeekend || isPeakHour) {
    questions.push({
      id: "crowd", icon: "🚦",
      question: `今天是${isWeekend ? "周末" : "出行高峰期"}，人流较多，建议安排 2-3 个地点，你觉得呢？`,
      options: [
        { label: "好呀，精简一些", value: "compact" },
        { label: "看你安排", value: "auto" },
        { label: "再多几个吧", value: "more" },
      ],
    });
  }

  if (goals.includes("foodie") && trip.people >= 3) {
    questions.push({
      id: "food_style", icon: "🍽️",
      question: `你们 ${trip.people} 个人一起，有口味偏好吗？`,
      options: [
        { label: "本地特色优先", value: "local" },
        { label: "人气网红店优先", value: "popular" },
        { label: "都可以，随机", value: "any" },
      ],
    });
  }

  if (questions.length === 0) {
    questions.push({
      id: "pace", icon: "🎯",
      question: "今天出行节奏想要怎样？",
      options: [
        { label: "慢慢来，放松为主", value: "relaxed" },
        { label: "紧凑一些，多转几处", value: "packed" },
        { label: "随缘就好", value: "auto" },
      ],
    });
  }
  return questions.slice(0, 2);
}

function buildFollowUpSupplement(answers: Record<string, string>): string {
  const parts: string[] = [];
  const map: Record<string, Record<string, string>> = {
    weather:    { prefer_outdoor: "尽量安排户外场景", mixed: "室内外均可", prefer_indoor: "偏向室内场景" },
    crowd:      { compact: "地点精简 2-3 个即可", auto: "地点数量你来定", more: "可以多安排几个地点" },
    food_style: { local: "美食偏向本地特色", popular: "美食偏向人气网红店", any: "美食随机推荐" },
    pace:       { relaxed: "节奏轻松慢游", packed: "节奏紧凑多转", auto: "节奏随缘" },
  };
  for (const [qid, val] of Object.entries(answers)) {
    const hint = map[qid]?.[val];
    if (hint) parts.push(hint);
  }
  return parts.length > 0 ? "，" + parts.join("，") : "";
}

// ── 追问卡片组件 ──────────────────────────────────────────────
interface SmartFollowUpProps {
  questions: FollowUpQuestion[];
  onAllAnswered: (answers: Record<string, string>) => void;
  readonly?: boolean;
}

function SmartFollowUp({ questions, onAllAnswered, readonly = false }: SmartFollowUpProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [showQuestions, setShowQuestions] = useState(false);
  const sentRef = useRef(false);

  useEffect(() => {
    const t = setTimeout(() => setShowQuestions(true), 1200);
    return () => clearTimeout(t);
  }, []);

  function handleSelect(qid: string, value: string) {
    if (readonly) return;
    const newAnswers = { ...answers, [qid]: value };
    setAnswers(newAnswers);
    if (!sentRef.current && questions.every((q) => newAnswers[q.id] !== undefined)) {
      sentRef.current = true;
      onAllAnswered(newAnswers);
    }
  }

  return (
    <div className="followup-steps">
      {!showQuestions && (
        <div className="bubble bubble-assistant typing-dots followup-thinking">
          <span /><span /><span />
        </div>
      )}
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

  useEffect(() => {
    setTimeout(() => textareaRef.current?.focus(), 300);
  }, []);

  return (
    <div className="plan-welcome">
      <button type="button" className="plan-welcome-back" onClick={onBack}>
        <ChevronLeft size={20} />
      </button>
      <div className="plan-welcome-body">
        <div className="plan-welcome-hero">
          <Navigation size={36} strokeWidth={1.5} className="plan-welcome-icon" />
          <h1 className="plan-welcome-title">今天想去哪儿？</h1>
          <p className="plan-welcome-sub">告诉 AI 你的想法，立刻生成专属行程</p>
        </div>

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

// ── 行程设置面板 ──────────────────────────────────────────────
interface TripSetupPanelProps {
  profile: OnboardingProfile;
  onStart: (trip: TripConstraints) => void;
  onSkip: () => void;
  presetGoals?: string[];
}

function TripSetupPanel({ profile, onStart, onSkip, presetGoals }: TripSetupPanelProps) {
  const [trip, setTrip] = useState<TripConstraints>(() => {
    const goals = presetGoals?.length
      ? presetGoals.filter((s) => TODAY_GOAL_OPTIONS.some((o) => o.key === s))
      : profile.scenarios.filter((s) => TODAY_GOAL_OPTIONS.some((o) => o.key === s)).slice(0, 2);
    return { ...DEFAULT_TRIP_CONSTRAINTS, today_goals: goals };
  });
  const [locating, setLocating] = useState(true);
  const [locateResult, setLocateResult] = useState<"ok" | "manual" | "pending">("pending");
  const [cityExpanded, setCityExpanded] = useState(false);
  const [customGoal, setCustomGoal] = useState("");

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

  useEffect(() => {
    setLocating(true);
    set("location", MOCK_LOCATION);
    set("city", "北京");
    detectCity().then((city) => {
      setLocating(false);
      if (city) set("city", city);
      setLocateResult("ok");
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="setup-page">
      <div className="setup-page-nav">
        <button type="button" className="setup-page-back" onClick={onSkip} aria-label="返回">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <span className="setup-page-nav-title">创建今日行程</span>
        <div style={{ width: 36 }} />
      </div>

      <div className="setup-panel">
        <div className="setup-header">
          <Navigation size={28} strokeWidth={1.5} className="setup-emoji" />
          <h2 className="setup-title">今天想去哪儿玩？</h2>
          <p className="setup-subtitle">告诉我这次的安排，AI 直接给你出方案</p>
        </div>

        <div className="setup-fields">
          {/* 出发位置 */}
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
                  <button type="button" className="setup-city-toggle" onClick={() => setCityExpanded(true)}>
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
                      if (val) set("location", val);
                      setCityExpanded(false);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        const val = (e.target as HTMLInputElement).value.trim();
                        if (val) set("location", val);
                        setCityExpanded(false);
                      }
                      if (e.key === "Escape") setCityExpanded(false);
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

          {/* 出行时间 */}
          <div className="setup-field">
            <div className="setup-field-label"><Clock size={13} /> 出行时间 <span className="setup-optional">可不填</span></div>
            <div className="setup-time-row">
              <label className="setup-time-label">出发</label>
              <input type="time" className="setup-time-input" value={trip.start_time} onChange={(e) => set("start_time", e.target.value)} />
              <span className="setup-time-sep">—</span>
              <label className="setup-time-label">结束</label>
              <input type="time" className="setup-time-input" value={trip.end_time} onChange={(e) => set("end_time", e.target.value)} />
              {(trip.start_time || trip.end_time) && (
                <button type="button" className="setup-time-clear" onClick={() => { set("start_time", ""); set("end_time", ""); }}>
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

        <div className="setup-footer">
          <button type="button" className="setup-btn-start" onClick={() => onStart(trip)}>
            开始规划 →
          </button>
        </div>
      </div>
    </div>
  );
}

// ── 状态标签组件 ──────────────────────────────────────────────
function StatusBadge({ status }: { status: "planning" | "ready" | "active" }) {
  if (status === "planning") return <span className="planner-status-badge planning">AI 规划中</span>;
  if (status === "ready") return <span className="planner-status-badge ready">方案已就绪</span>;
  return <span className="planner-status-badge active">行程进行中</span>;
}

// ── 主页面 ────────────────────────────────────────────────────
export function PlannerPage({ profile, onResetProfile, preset, onPresetConsumed, onBackToHome, onTripFinished, onNewTrip, onActiveTripChange, activeTrip, onSaveTrip, initialMsg, onOpenSidebar, onSendReady, onInjectText, onDisabledChange, onViewModeChange }: PlannerPageProps) {
  const { messages, response, liveTrace, loading, error, lastRequest, send, inject, reset, snapshot, restore, answerClarify, patchRouteStops } = useChat();
  const [localProfile, setLocalProfile] = useState<OnboardingProfile>(profile);
  const [trip, setTrip] = useState<TripConstraints | null>(null);
  const [showSetup, setShowSetup] = useState(!(initialMsg ?? preset?.initialMsg));
  const [viewMode, setViewMode] = useState<PlannerViewMode>("chat");

  // 追问状态
  const [followUp, setFollowUp] = useState<{ trip: TripConstraints; questions: FollowUpQuestion[] } | null>(null);

  // 地图相关状态
  const [activePoi, setActivePoi] = useState<string | null>(null);
  const [activeRouteIndex, setActiveRouteIndex] = useState(0);
  const [mapRouteIndex, setMapRouteIndex] = useState<number>(-1);
  const [mapStops, setMapStops] = useState<RouteStop[] | null>(null);
  const routeBoardPanelRef = useRef<HTMLDivElement>(null);
  const [routeBoardPanelHeight, setRouteBoardPanelHeight] = useState(0);
  const [isRouteBoardPanelCollapsed, setIsRouteBoardPanelCollapsed] = useState(false);

  // 编辑 Sheet 状态
  const [showEditSheet, setShowEditSheet] = useState(false);
  const [editRouteIndex, setEditRouteIndex] = useState(0);
  const [editableRoutes, setEditableRoutes] = useState<Route[]>([]);

  // 选中的路线（用于路线看板视图）
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);

  // 是否已开始出发；activeTripRoute 独立于当前对话，便于新建会话后继续查看进行中的行程
  const [tripStarted, setTripStarted] = useState(false);
  const [activeTripRoute, setActiveTripRoute] = useState<Route | null>(null);
  const [startBlockedNotice, setStartBlockedNotice] = useState(false);
  const startBlockedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 是否从侧边栏直接进入（方案就绪后自动跳看板）
  const directBoardRef = useRef(false);
  // 历史会话需要展示其完整对话内容，路线卡只显示对应历史路线。
  const [historyRouteId, setHistoryRouteId] = useState<string | null>(null);

  // 消费来自首页的预设参数
  useLayoutEffect(() => {
    if (!preset) return;
    directBoardRef.current = !!preset.directBoard;
    if (preset.conversation) {
      restore(preset.conversation);
      const restoredRoutes = preset.conversation.response?.routes ?? [];
      const restoredRoute = restoredRoutes.find((route) => route.route_id === preset.routeId)
        ?? restoredRoutes.find((route) => route.title === preset.title)
        ?? restoredRoutes[0]
        ?? null;
      setTrip(null);
      setFollowUp(null);
      setShowSetup(false);
      setHistoryRouteId(restoredRoute?.route_id ?? null);
      setSelectedRouteId(restoredRoute?.route_id ?? null);
      setActiveRouteIndex(restoredRoute ? Math.max(restoredRoutes.indexOf(restoredRoute), 0) : -1);
      setMapRouteIndex(restoredRoute ? Math.max(restoredRoutes.indexOf(restoredRoute), 0) : -1);
      setMapStops(restoredRoute ? [...restoredRoute.stops] : null);
      // 历史记录打开后先完整展示已保存的对话；用户可自行进入路线看板。
      setViewMode("chat");
    } else if (preset.directBoard && activeTrip && preset.title === activeTrip.title) {
      setHistoryRouteId(null);
      setActiveTripRoute(activeTrip);
      setTripStarted(true);
      setSelectedRouteId(activeTrip.route_id);
      setActiveRouteIndex(0);
      setMapRouteIndex(0);
      setMapStops([...activeTrip.stops]);
      setShowSetup(false);
      setViewMode("board");
    } else if (preset.initialMsg) {
      const msg = preset.initialMsg;
      setHistoryRouteId(null);
      reset();
      setTrip(null);
      setFollowUp(null);
      setShowSetup(false);
      Promise.resolve().then(() => {
        send(msg, localProfile, DEFAULT_TRIP_CONSTRAINTS);
      });
    } else {
      setHistoryRouteId(null);
      setShowSetup(true);
      setTrip(null);
      setFollowUp(null);
    }
    onPresetConsumed?.();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset, activeTrip]);

  // 首次挂载：如果有 initialMsg 则自动进入对话
  const initialMsgRef = useRef<string | undefined>(initialMsg);
  useEffect(() => {
    const msg = initialMsgRef.current;
    if (!msg) return;
    initialMsgRef.current = undefined;
    reset();
    send(msg, localProfile, DEFAULT_TRIP_CONSTRAINTS);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 注册 send 函数给 App 层全局输入栏 ──
  useEffect(() => {
    onSendReady?.((msg: string) => {
      send(msg, localProfile, trip ?? DEFAULT_TRIP_CONSTRAINTS);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localProfile, trip]);

  // ── 上报输入栏禁用状态（loading 或 showSetup 时禁用）──
  useEffect(() => {
    onDisabledChange?.(loading || showSetup);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, showSetup]);

  // ── 通知 App 层视图模式变化（board 时隐藏输入栏）──
  useEffect(() => {
    onViewModeChange?.(viewMode);
  }, [viewMode, onViewModeChange]);

  // ── 视图切换逻辑 ──
  const hasRoutes = (response?.routes?.length ?? 0) > 0;
  const displayedRoutes = historyRouteId
    ? (response?.routes ?? []).filter((route) => route.route_id === historyRouteId)
    : (response?.routes ?? []);

  // 当有方案时，自动选中第一个切换到路线视图
  useEffect(() => {
    if (hasRoutes && !loading) {
      setActiveRouteIndex(0);
      setMapRouteIndex(-1);
      setMapStops(null);
      setEditableRoutes(response!.routes.map((r) => ({ ...r, stops: [...r.stops] })));
      // 默认选中第一个方案用于路线看板展示
      if (!selectedRouteId) {
        setSelectedRouteId(response!.routes[0].route_id);
      }
      // 如果是从侧边栏直接进入的，方案就绪后自动跳到看板视图
      if (directBoardRef.current) {
        setMapRouteIndex(0);
        setMapStops([...response!.routes[0].stops]);
        setViewMode("board");
        directBoardRef.current = false;
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [response?.routes?.length, loading]);

  // ── 事件处理函数 ──
  function showStartBlockedNotice() {
    if (startBlockedTimerRef.current) clearTimeout(startBlockedTimerRef.current);
    setStartBlockedNotice(true);
    startBlockedTimerRef.current = setTimeout(() => {
      setStartBlockedNotice(false);
      startBlockedTimerRef.current = null;
    }, 2600);
  }

  function handleStart(newTrip: TripConstraints) {
    setTrip(newTrip);
    setShowSetup(false);
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

  function handleSkip() {
    onBackToHome?.();
  }

// 从对话视图切换到路线看板
function handleEnterRouteBoard(routeId?: string) {
if (routeId) {
setSelectedRouteId(routeId);
      const idx = (response?.routes ?? []).findIndex((r) => r.route_id === routeId);
      if (idx !== -1) {
        setActiveRouteIndex(idx);
        setMapRouteIndex(idx);
        setMapStops([...response!.routes[idx].stops]);
      }
    }
    setViewMode("board");
  }

  // 从路线看板返回对话
  function handleBackToChat() {
    setViewMode("chat");
  }

  // 行程进行中时，从对话快速回到当前路线看板
  function handleReturnToActiveTrip() {
    const route = activeTripRoute ?? selectedRoute;
    if (!route) return;
    const idx = (response?.routes ?? []).findIndex((item) => item.route_id === route.route_id);
    setActiveRouteIndex(idx);
    setMapRouteIndex(idx);
    setMapStops([...route.stops]);
    setSelectedRouteId(route.route_id);
    setViewMode("board");
  }

  // 地图 POI 被点击
  function handlePoiClick(poiId: string) {
    setActivePoi(poiId);
  }

  const handleRouteOptimizeAction = useCallback((action: string, routeId: string) => {
    const routeTitle = response?.routes?.find((route) => route.route_id === routeId)?.title ?? routeId;
    const requestByAction: Record<string, string> = {
      budget: `请为「${routeTitle}」压缩预算`,
      queue: `请为「${routeTitle}」避开高排队地点`,
      walk: `请为「${routeTitle}」减少步行距离`,
      relax: `请为「${routeTitle}」安排得更轻松一些，减少地点并留出更多休息时间`,
    };
    const message = requestByAction[action];
    if (!message) return;
    send(message, localProfile, trip ?? DEFAULT_TRIP_CONSTRAINTS);
    setViewMode("chat");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localProfile, trip, response?.routes]);

  const handlePoiAction = useCallback((action: PoiAction, routeId: string) => {
    const routeTitle = response?.routes?.find((r) => r.route_id === routeId)?.title ?? routeId;
    if (action.type === "talk_ai") {
      const hint = `【${routeTitle}】中的「${action.poiName}」`;
      setViewMode("chat");
      onInjectText?.(hint);
      return;
    }
    const name = `【${routeTitle}】`;
    let msg = "";
    if (action.type === "swap_same") msg = `${name}中的「${action.poiName}」我不满意，帮我换一个同类型的地点`;
    else if (action.type === "swap_as") msg = `${name}中的「${action.poiName}」帮我换成${action.category}类型的地点`;
    else if (action.type === "remove") msg = `${name}中去掉「${action.poiName}」，帮我重新衔接路线`;
    if (msg) {
      send(msg, localProfile, trip ?? DEFAULT_TRIP_CONSTRAINTS);
      setViewMode("chat");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localProfile, trip, response?.routes, onInjectText]);

  function handleResetProfile() {
    reset();
    onResetProfile();
  }

  // ── 新建行程：清空规划上下文后回首页；进行中路线由应用层继续展示 ──
  function handleNewTrip() {
    const routes = response?.routes ?? [];
    const routeToSave = selectedRouteId
      ? routes.find((route) => route.route_id === selectedRouteId) ?? routes[0]
      : routes[0];
    if (routeToSave && !activeTrip) {
      onSaveTrip?.(routeToSave, snapshot());
    }
    reset();
    setTrip(null);
    setFollowUp(null);
    setShowSetup(false);
    setSelectedRouteId(null);
    setActiveRouteIndex(-1);
    setMapRouteIndex(-1);
    setMapStops(null);
    setViewMode("chat");
    onNewTrip?.();
  }

  // 获取当前选中的路线
  const selectedRoute = selectedRouteId
    ? (response?.routes ?? []).find((r) => r.route_id === selectedRouteId) ?? null
    : null;

// 获取当前看板路线；进行中的行程独立保留，避免新建会话后丢失。
const boardRoute = selectedRoute ?? activeTripRoute;
// 出发/结束状态必须与当前展示的方案一一对应，不能影响其他方案。
const isBoardRouteActive = Boolean(activeTrip && boardRoute && activeTrip.route_id === boardRoute.route_id);

// ── 状态判断 ──
const statusBadge: "planning" | "ready" | "active" = loading ? "planning" : isBoardRouteActive ? "active" : hasRoutes ? "ready" : "planning";
const routeTitle = boardRoute?.title ?? (response?.routes?.[0]?.title ?? "");

  // ── 路线看板底部面板高度变化时，重算地图可视安全区 ──
  useEffect(() => {
    if (viewMode !== "board") return;
    const panel = routeBoardPanelRef.current;
    if (!panel) return;

    const updatePanelHeight = () => setRouteBoardPanelHeight(Math.round(panel.getBoundingClientRect().height));
    updatePanelHeight();
    const observer = new ResizeObserver(updatePanelHeight);
    observer.observe(panel);
    return () => observer.disconnect();
  }, [viewMode, selectedRouteId, mapStops]);

  // ── 渲染 ──
  return (
    <div className={`planner-shell${viewMode === "board" ? " planner-shell--board" : ""}`}>
      {/* ── 路线看板视图 (Route Board View) ── */}
      {viewMode === "board" && (
        <div className="route-board-view">
          {/* 全屏地图背景 */}
          <div className="route-board-map">
            <MapPanel
              routes={boardRoute ? [boardRoute] : (response?.routes ?? [])}
              activeRouteIndex={boardRoute ? 0 : mapRouteIndex}
              activePoi={activePoi}
              onPoiClick={handlePoiClick}
              sheetSnap="peek"
              liveStops={mapStops ?? boardRoute?.stops}
              showUserLocation
              isBoardView
              boardOverlayHeight={routeBoardPanelHeight}
            />
          </div>

          {/* 顶部导航条 */}
          <header className="route-board-topbar">
            <button
              type="button"
              className="route-board-back"
              onClick={handleBackToChat}
              aria-label="返回对话"
            >
              <ChevronLeft size={20} />
            </button>
            <span className="route-board-title">{routeTitle}</span>
<span className={`route-board-status${isBoardRouteActive ? " route-board-status--active" : ""}`}>
{isBoardRouteActive ? "行程进行中" : "方案进行中"}
            </span>
          </header>

          {/* 底部信息面板 */}
          <div ref={routeBoardPanelRef} className={`route-board-panel${isRouteBoardPanelCollapsed ? " route-board-panel--collapsed" : ""}`}>
            <button
              type="button"
              className="route-board-panel-handle"
              onClick={() => setIsRouteBoardPanelCollapsed((collapsed) => !collapsed)}
              aria-label={isRouteBoardPanelCollapsed ? "展开行程详情" : "折叠行程详情"}
              aria-expanded={!isRouteBoardPanelCollapsed}
            />

            {/* 详细时间轴 */}
            <div className="route-board-timeline">
              {boardRoute && (
                <RouteCompare
                  routes={[boardRoute]}
                  loading={false}
                  autoExpand
                  onAction={handleRouteOptimizeAction}
                  onPoiAction={handlePoiAction}
                  onTripFinished={(route, avgScore) => onTripFinished?.(route, avgScore, snapshot())}
                  onRoutePreview={(routeId) => {
                    const idx = (response?.routes ?? []).findIndex((r) => r.route_id === routeId);
                    if (idx !== -1) {
                      setActiveRouteIndex(idx);
                      setMapRouteIndex(idx);
                      setMapStops([...response!.routes[idx].stops]);
                    }
                  }}
                  onLiveStopsChange={(routeId, newStops) => {
                    setMapStops(newStops);
                    const idx = (response?.routes ?? []).findIndex((r) => r.route_id === routeId);
                    if (idx !== -1) setMapRouteIndex(idx);
                    patchRouteStops(routeId, newStops);
                  }}
                />
              )}
            </div>

            {startBlockedNotice && (
              <div className="route-board-start-blocked-notice" role="status">
                先停止当前行程后再出发
              </div>
            )}

            {/* 底部双操作栏 */}
            <div className="route-board-actions">
              <button
                type="button"
                className="route-board-action route-board-action--ghost"
                onClick={handleBackToChat}
              >
                <MessageSquare size={16} />
                返回修改行程...
              </button>
{!isBoardRouteActive ? (
<button
                  type="button"
                  className="route-board-action route-board-action--primary"
                  onClick={() => {
                    if (!selectedRoute) return;
                    if (activeTrip && !isBoardRouteActive) {
                      showStartBlockedNotice();
                      return;
                    }
                    if (selectedRoute) {
                      setTripStarted(true);
                      const startedRoute = { ...selectedRoute, stops: [...selectedRoute.stops] };
                      setActiveTripRoute(startedRoute);
                      onActiveTripChange?.(startedRoute);
                      const idx = (response?.routes ?? []).findIndex((r) => r.route_id === selectedRoute.route_id);
                      if (idx !== -1) {
                        setActiveRouteIndex(idx);
                        setMapRouteIndex(idx);
                        setMapStops([...response!.routes[idx].stops]);
                      }
                    }
                  }}
                >
                  <Rocket size={16} />
                  选择出发
                </button>
              ) : (
                <button
                  type="button"
                  className="route-board-action route-board-action--danger"
                  onClick={() => {
                    setTripStarted(false);
                    setActiveTripRoute(null);
                    onActiveTripChange?.(null);
                  }}
                >
                  <X size={16} />
                  结束行程
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── 对话视图 (Chat View) ── */}
      {viewMode === "chat" && (
        <div className="planner-chat-view">
          {/* 顶部导航 */}
          <header className="planner-chat-topbar">
            <button
              type="button"
              className="home-menu-btn"
              onClick={() => onOpenSidebar?.()}
              aria-label="打开菜单"
            >
              <Menu size={20} />
            </button>
            {routeTitle && (
              <span className="planner-chat-title">{routeTitle}</span>
            )}
            {!routeTitle && hasRoutes && (
              <span className="planner-chat-title">{response?.routes?.[0]?.title}</span>
            )}
            <button
              type="button"
              className="planner-new-trip-btn"
              onClick={handleNewTrip}
              aria-label="新建行程"
            >
              <Plus size={20} />
            </button>
          </header>

          {/* 全屏内容区 */}
          <div className="planner-chat-content">
            {activeTripRoute && (
              <div className="planner-chat-active-trip-banner">
                <div className="planner-chat-active-trip-copy">
                  <span className="planner-chat-active-trip-kicker">当前行程</span>
                  <span className="planner-chat-active-trip-name">{routeTitle || "行程进行中"}</span>
                </div>
                <button type="button" className="planner-chat-active-trip-button" onClick={handleReturnToActiveTrip}>
                  <Navigation size={15} />
                  查看当前行程
                </button>
              </div>
            )}
            {/* 对话内容 */}
            <div className="planner-chat-scroll">
              <ChatPanel
                messages={messages}
                loading={loading}
                error={error}
                onClarify={(answer, extra) => answerClarify(answer, localProfile, trip ?? DEFAULT_TRIP_CONSTRAINTS, undefined, extra)}
                afterFirstUserMessage={
                  (followUp && !loading) ? (
                    <SmartFollowUp
                      questions={followUp.questions}
                      onAllAnswered={handleFollowUpConfirm}
                    />
                  ) : undefined
                }
                beforeLoadingBubble={
                  <AgentTrace
                    steps={liveTrace}
                    loading={loading}
                    userInput={[...messages].reverse().find((m) => m.role === "user")?.content}
                  />
                }
                afterLastAssistant={
                  hasRoutes ? (
                    <div className="chat-inline-routes">
                      <RouteCompare
                        routes={displayedRoutes}
                        loading={false}
                        onAction={handleRouteOptimizeAction}
                        onPoiAction={handlePoiAction}
                        onTripFinished={(route, avgScore) => onTripFinished?.(route, avgScore, snapshot())}
                        onRoutePreview={(routeId) => handleEnterRouteBoard(routeId)}
                        onLiveStopsChange={(routeId, newStops) => {
                          setMapStops(newStops);
                          const idx = (response?.routes ?? []).findIndex((r) => r.route_id === routeId);
                          if (idx !== -1) setMapRouteIndex(idx);
                          patchRouteStops(routeId, newStops);
                        }}
                      />
                    </div>
                  ) : undefined
                }
              />
            </div>

          </div>

          {/* 规划欢迎首屏 */}
          {showSetup && (
            <PlanningWelcomeScreen
              onBack={handleSkip}
              onSend={(msg) => {
                reset();
                setShowSetup(false);
                send(msg, localProfile, DEFAULT_TRIP_CONSTRAINTS);
              }}
            />
          )}
        </div>
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
