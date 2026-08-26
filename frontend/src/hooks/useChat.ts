import { useRef, useState } from "react";
import { getChatSessionId, resetChatSession, sendChatMessageStream, setChatSessionId } from "../api/chatApi";
import type { AgentTraceStep, ChatResponse, ClarificationGroup, Route } from "../api/types";
import type { OnboardingProfile, TripConstraints } from "./useOnboarding";
import { waitForGps } from "../utils/gpsCache";

export interface ChatMessage {
  role: "user" | "assistant" | "trace" | "clarify";
  content: string;
  timestamp: number;
  agentTrace?: AgentTraceStep[];
  /** 当前轮次的用户输入原文，用于 AgentTrace 叙述中「用户说…」开头 */
  agentUserInput?: string;
  /** clarify 角色专用：AI 追问的问题文本（兜底单问题） */
  clarifyQuestion?: string;
  /** clarify 角色专用：后端返回的多组追问（优先使用） */
  clarificationGroups?: ClarificationGroup[];
  /** clarify 角色专用：用户已填写的回答（填写后变为只读展示） */
  clarifyAnswer?: string;
  /** clarify 角色专用：用户选择的各组答案 label 汇总文本，用于展示已回答状态 */
  clarifyAnswerLabels?: string;
  /** 此轮回复生成的方案；用于将方案卡固定渲染在对应回复之后。 */
  routeBatch?: Route[];
}

export interface ChatSessionSnapshot {
  sessionId: string;
  messages: ChatMessage[];
  response: ChatResponse | null;
  /** 尚未完成的一轮模型思考；切换历史时保留在原消息位置。 */
  pendingTrace?: AgentTraceStep[];
  /** pendingTrace 对应的用户输入，用于展示思考过程的上下文。 */
  pendingUserInput?: string;
  /** 此会话是否仍有后台请求在生成。 */
  isPending?: boolean;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [liveTrace, setLiveTrace] = useState<AgentTraceStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRequest, setLastRequest] = useState<Record<string, unknown> | null>(null);
  const hasSentProfile = useRef(false);
  const activeProfileSigRef = useRef<string | null>(null);
  const requestSeqRef = useRef(0);
  // 按会话追踪未完成请求，切回原会话时可重新接管其流式过程。
  const inFlightRequestsRef = useRef(new Map<string, number>());
  const inFlightRef = useRef(false);
  const lastProfileSigRef = useRef<string | null>(null);

  function buildProfileSignature(profile?: OnboardingProfile) {
    if (!profile) return null;
    return JSON.stringify({
      user_id: profile.user_id,
      scenarios: profile.scenarios,
      preferences: profile.preferences,
      avoid_tags: profile.avoid_tags,
      budget_level: profile.budget_level,
      preference_weights: profile.preference_weights,
    });
  }

  /**
   * 服务端的 route_id 只保证单次响应内唯一；为每轮结果添加本地轮次后缀，
   * 让后续规划可以与此前的方案并存，而不是覆盖。
   */
  function createRouteBatch(incoming: Route[], requestSeq: number): Route[] {
    const routeIdSuffix = `__turn_${requestSeq}`;
    return incoming.map((route) => ({
      ...route,
      stops: [...route.stops],
      route_id: `${route.route_id}${routeIdSuffix}`,
    }));
  }

  function mergeRoutes(existing: Route[], batch: Route[]): Route[] {
    const batchIds = new Set(batch.map((route) => route.route_id));
    // 流式 routes 事件与 final 事件会各到达一次；同一轮只保留最终那一份。
    return [...existing.filter((route) => !batchIds.has(route.route_id)), ...batch];
  }

  function mergeResponse(previous: ChatResponse | null, next: ChatResponse, batch: Route[]): ChatResponse {
    return {
      ...next,
      routes: mergeRoutes(previous?.routes ?? [], batch),
    };
  }

  async function send(
    message: string,
    profile?: OnboardingProfile,
    trip?: TripConstraints,
    silent = false,
    options: Record<string, unknown> = {},
    onSettled?: (snapshot: ChatSessionSnapshot) => void,
    onProgress?: (snapshot: ChatSessionSnapshot) => void,
  ) {
    if (inFlightRef.current) return;

    if (!silent) {
      const userMsg: ChatMessage = { role: "user", content: message, timestamp: Date.now() };
      setMessages((prev) => [...prev, userMsg]);
    }
    // 保留先前方案，让新一轮规划的加载过程不清空已经生成的方案卡片。
    setLiveTrace([]);
    setLoading(true);
    setError(null);
    inFlightRef.current = true;

    const requestSeq = ++requestSeqRef.current;
    // 请求开始时锁定其所属会话。即使用户随后切换历史记录，完成结果也能写回正确的对话。
    const requestSessionId = getChatSessionId();
    inFlightRequestsRef.current.set(requestSessionId, requestSeq);
    const requestMessages = silent
      ? messages
      : [...messages, { role: "user" as const, content: message, timestamp: Date.now() }];
    const requestResponse = response;
    const requestTraceRef = { current: [] as AgentTraceStep[] };

    try {
    const profileSig = buildProfileSignature(profile);
    activeProfileSigRef.current = profileSig;
    const includeProfile =
      !hasSentProfile.current ||
      (profileSig !== null && profileSig !== lastProfileSigRef.current);
      const locationOptions = await getCurrentLocationOptions();

      // 记录本次发送的请求体快照，供 Debug Panel 展示
      setLastRequest({
        session_id: "(当前会话ID)",
        message,
        ...(trip?.city ? { trip_city: trip.city } : { trip_city: "(未传，后端追问)" }),
        start_lat: (locationOptions as Record<string, unknown>).start_lat ?? null,
        start_lng: (locationOptions as Record<string, unknown>).start_lng ?? null,
        preferences: profile?.preferences ?? [],
        scenarios: profile?.scenarios ?? [],
        avoid_tags: profile?.avoid_tags ?? [],
        ...options,
      });

      const res = await sendChatMessageStream(
        message,
        profile,
        includeProfile,
        (step) => {
          // 已切到其他历史会话时，旧请求的流式思考不应污染当前会话 UI。
          if (requestSeq === requestSeqRef.current) {
            setLiveTrace((prev) => [...prev, step]);
          }
          requestTraceRef.current = [...requestTraceRef.current, step];
          onProgress?.({
            sessionId: requestSessionId,
            messages: requestMessages,
            response: requestResponse,
            pendingTrace: requestTraceRef.current,
            pendingUserInput: message,
            isPending: true,
          });
        },
        trip,
        { ...locationOptions, ...options },
        (routes) => {
          // 路线流在后台仍可继续接收，但只允许当前会话更新可见状态。
          if (requestSeq !== requestSeqRef.current) return;
          const routeBatch = createRouteBatch(routes, requestSeq);
          setResponse((prev) => ({
            session_id: prev?.session_id ?? "",
            message: prev?.message ?? "",
            need_clarification: prev?.need_clarification ?? false,
            clarifying_question: prev?.clarifying_question ?? null,
            clarification_type: prev?.clarification_type ?? null,
            clarification_groups: prev?.clarification_groups ?? [],
            inferred_context: prev?.inferred_context ?? {},
            intent: prev?.intent ?? null,
            user_profile: prev?.user_profile ?? null,
            agent_trace: prev?.agent_trace ?? [],
            routes: mergeRoutes(prev?.routes ?? [], routeBatch),
          }));
        },
      );

      if (includeProfile) {
        hasSentProfile.current = true;
        lastProfileSigRef.current = profileSig;
      }

      const routeBatch = createRouteBatch(res.routes ?? [], requestSeq);
      const completedResponse = mergeResponse(requestResponse, res, routeBatch);
      const completedMessages: ChatMessage[] = [...requestMessages];
      if (res.need_clarification) {
        completedMessages.push(
          { role: "assistant", content: res.message || "我想多了解一点，帮你规划得更准", timestamp: Date.now() },
          {
            role: "clarify",
            content: "",
            timestamp: Date.now() + 1,
            clarificationGroups: res.clarification_groups?.length ? res.clarification_groups : undefined,
            clarifyQuestion: res.clarifying_question ?? "",
          },
        );
      } else if (res.message?.trim()) {
        completedMessages.push({ role: "assistant", content: res.message, timestamp: Date.now(), routeBatch: routeBatch.length ? routeBatch : undefined });
      } else if (routeBatch.length) {
        completedMessages.push({ role: "trace", content: "", timestamp: Date.now(), routeBatch });
      }
      const completedSnapshot: ChatSessionSnapshot = {
        sessionId: requestSessionId,
        messages: completedMessages,
        response: completedResponse,
        isPending: false,
      };

      // 切换历史会使 requestSeq 失效，但网络请求无需取消；完成后把结果回写其原始会话。
      if (requestSeq !== requestSeqRef.current) {
        onSettled?.(completedSnapshot);
        return;
      }

      setResponse((prev) => mergeResponse(prev, res, routeBatch));
      setLiveTrace(res.agent_trace);

      if (res.need_clarification) {
        // 追问轮次：先插一条友好的前置气泡，再插入 clarify 卡片
        const preMsg: ChatMessage = {
          role: "assistant",
          content: res.message || "我想多了解一点，帮你规划得更准",
          timestamp: Date.now(),
          // agent_trace 挂在前置气泡上展示，clarify 卡片本身不再重复
          agentTrace: res.agent_trace && res.agent_trace.length > 0 ? res.agent_trace : undefined,
          agentUserInput: message,
        };
        const clarifyRecord: ChatMessage = {
          role: "clarify",
          content: "",
          timestamp: Date.now() + 1,
          // 优先使用多组追问，兜底用单问题文本
          clarificationGroups: res.clarification_groups && res.clarification_groups.length > 0
            ? res.clarification_groups
            : undefined,
          clarifyQuestion: res.clarifying_question ?? "",
        };
        setMessages((prev) => [...prev, preMsg, clarifyRecord]);
      } else {
        // 正常轮次：直接插入 assistant 回复气泡
        // agent_trace 挂在回复气泡上展示；若无回复文案则用 trace 类型（只渲染思考步骤，无气泡）
        const traceData = res.agent_trace && res.agent_trace.length > 0 ? res.agent_trace : undefined;
        const newMsgs: ChatMessage[] = [];

        if (res.message && res.message.trim()) {
          // 有回复文案：正常 assistant 气泡，挂 agent_trace
          newMsgs.push({
            role: "assistant",
            content: res.message,
            timestamp: Date.now(),
            agentTrace: traceData,
            agentUserInput: message,
            routeBatch: routeBatch.length > 0 ? routeBatch : undefined,
          });
        } else if (traceData || routeBatch.length > 0) {
          // 无回复文案时保留一个 trace 锚点，用于承载思考步骤或本轮方案卡片。
          newMsgs.push({
            role: "trace",
            content: "",
            timestamp: Date.now(),
            agentTrace: traceData,
            agentUserInput: message,
            routeBatch: routeBatch.length > 0 ? routeBatch : undefined,
          });
        }
        setMessages((prev) => [...prev, ...newMsgs]);
      }
    } catch (requestError) {
      if (requestSeq !== requestSeqRef.current) return;
      setError(requestError instanceof Error ? requestError.message : "请求失败，请检查后端是否启动");
    } finally {
      inFlightRequestsRef.current.delete(requestSessionId);
      if (requestSeq === requestSeqRef.current) {
        setLoading(false);
        inFlightRef.current = false;
      }
    }
  }

  /**
   * 用户回答追问：把最后一条 clarify 记录的 clarifyAnswer 填上（就地更新，不加新气泡），
   * 然后 silent=true 发起下一轮请求。
   * @param answer        发送给后端的消息文本
   * @param labelSummary  可选，用于在气泡中展示的已回答摘要（各选项 label 拼接）
   * @param clarifyValues 可选，用户选择的各选项 value 合并对象（如 {city, target_district}），
   *                      会作为 options 附加到下一轮请求，让后端直接拿到结构化字段
   */
  function answerClarify(
    answer: string,
    profile?: OnboardingProfile,
    trip?: TripConstraints,
    labelSummary?: string,
    clarifyValues?: Record<string, unknown>,
    onSettled?: (snapshot: ChatSessionSnapshot) => void,
    onProgress?: (snapshot: ChatSessionSnapshot) => void,
  ) {
    // 1. 找到最后一条 clarify 消息，填入回答
    setMessages((prev) => {
      const idx = [...prev].reverse().findIndex((m) => m.role === "clarify");
      if (idx === -1) return prev;
      const realIdx = prev.length - 1 - idx;
      return prev.map((m, i) =>
        i === realIdx
          ? { ...m, clarifyAnswer: answer, clarifyAnswerLabels: labelSummary ?? answer }
          : m,
      );
    });
    // 2. silent=true：不再往 messages 里额外插 user bubble
    //    把结构化 value 作为 options 附带，后端直接读取 city/target_district 等字段
    send(answer, profile, trip, true, clarifyValues ?? {}, onSettled, onProgress);
  }

  /** 在本地直接插入一条消息（用于欢迎语，不走网络） */
  function inject(role: "user" | "assistant", content: string) {
    const msg: ChatMessage = { role, content, timestamp: Date.now() };
    setMessages((prev) => [...prev, msg]);
  }

  /** 清空对话历史（重置 profile 后调用） */
  function reset() {
    setMessages([]);
    setResponse(null);
    setLiveTrace([]);
    setError(null);
    setLoading(false);
    hasSentProfile.current = false;
    lastProfileSigRef.current = null;
    activeProfileSigRef.current = null;
    requestSeqRef.current += 1;
    inFlightRef.current = false;
    resetChatSession();
  }

  /**
   * 当前会话的可恢复快照。
   * 历史记录只保留用户与助手的最终内容，不存 Agent 推理步骤或实时状态。
   */
  function snapshot(): ChatSessionSnapshot {
    return {
      sessionId: getChatSessionId(),
      messages: messages
        // 无文案的规划结果会挂在 trace 锚点上；保存这类锚点才能恢复该轮方案卡片。
        .filter((message) => message.role !== "trace" || message.routeBatch?.length)
        .map(({ agentTrace: _agentTrace, agentUserInput: _agentUserInput, ...message }) => message),
      response,
      pendingTrace: liveTrace,
      pendingUserInput: loading ? [...messages].reverse().find((message) => message.role === "user")?.content : undefined,
      isPending: loading,
    };
  }

  /** 恢复已完成会话。恢复过程不触发接口请求，也不会展示实时 Agent 思考态。 */
  function restore(saved: ChatSessionSnapshot) {
    const pendingRequestSeq = saved.isPending ? inFlightRequestsRef.current.get(saved.sessionId) : undefined;
    // 若原请求仍在后台运行，回到该会话后重新接管其流式事件；否则保持后台回写模式。
    if (pendingRequestSeq !== undefined) {
      requestSeqRef.current = pendingRequestSeq;
    } else {
      requestSeqRef.current += 1;
    }
    inFlightRef.current = pendingRequestSeq !== undefined;
    setChatSessionId(saved.sessionId);
    // 兼容此前已保存的快照：恢复时同样剥离旧版本中残留的思考步骤。
    const restoredMessages = saved.messages
      // 只保留承载方案的 trace 锚点；其余实时思考步骤无需在历史中重放。
      .filter((message) => message.role !== "trace" || message.routeBatch?.length)
      .map(({ agentTrace: _agentTrace, agentUserInput: _agentUserInput, ...message }) => message);
    // 兼容本次改造前保存的历史：旧快照没有按轮次保存 routeBatch，
    // 将完整路线回填至最后一条助手回复，确保打开历史仍能看到全部方案。
    if (!restoredMessages.some((message) => message.routeBatch?.length) && saved.response?.routes?.length) {
      const lastAssistantIndex = [...restoredMessages].map((message) => message.role).lastIndexOf("assistant");
      if (lastAssistantIndex >= 0) {
        restoredMessages[lastAssistantIndex] = {
          ...restoredMessages[lastAssistantIndex],
          routeBatch: saved.response.routes,
        };
      }
    }
    setMessages(restoredMessages);
    setResponse(saved.response);
    // 正在后台生成的会话恢复后，继续在原消息位置展示已收到的思考步骤。
    setLiveTrace(saved.pendingTrace ?? []);
    setLoading(Boolean(saved.isPending));
    setError(null);
    hasSentProfile.current = true;
    lastProfileSigRef.current = activeProfileSigRef.current;
  }

  /**
   * 直接修改底层 response.routes 中某条路线的 stops（本地删除/排序等操作）。
   * routeId 对应要修改的路线，newStops 是更新后的站点列表。
   */
  function patchRouteStops(routeId: string, newStops: import("../api/types").RouteStop[]) {
    setResponse((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        routes: prev.routes.map((r) =>
          r.route_id === routeId ? { ...r, stops: newStops } : r
        ),
      };
    });
  }

  return { messages, response, liveTrace, loading, error, lastRequest, send, inject, reset, snapshot, restore, answerClarify, patchRouteStops };
}

// 默认起点：北京市西城区西单
const DEFAULT_START = {
  start_location_name: "北京市西城区西单",
  start_lat: 39.9072,
  start_lng: 116.3740,
  current_lat: 39.9072,
  current_lng: 116.3740,
};

async function getCurrentLocationOptions(): Promise<Record<string, unknown>> {
  // App.tsx 挂载时已发起 GPS 请求，这里等待最多 4 秒让缓存写入。
  // 用户只要在弹窗出现后的 4 秒内点了"允许"，坐标就能传给后端。
  const coords = await waitForGps(4000);
  if (coords) {
    return {
      current_lat: coords.lat,
      current_lng: coords.lng,
      start_lat:   coords.lat,
      start_lng:   coords.lng,
    };
  }
  // 无 GPS 时使用默认西单起点，避免后端追问城市
  return DEFAULT_START;
}
