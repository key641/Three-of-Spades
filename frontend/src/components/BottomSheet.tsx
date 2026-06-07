import { useRef, useState, useCallback, useEffect } from "react";

// ── 三档高度常量（相对于视口高度的百分比）────────────────────────
// peek  = 只露出手柄（地图几乎全屏）
// half  = 内容占 3/4，地图仅占 1/4（默认档位）
// full  = 全展开
export type SheetSnap = "peek" | "half" | "full";

const SNAP_VH: Record<SheetSnap, number> = {
  peek: 0.12,   // 视口 12%
  half: 0.75,   // 视口 75%（内容 3/4，地图 1/4）
  full: 0.92,   // 视口 92%
};

function snapFromVH(ratio: number): SheetSnap {
  if (ratio < 0.3)  return "peek";
  if (ratio < 0.84) return "half";
  return "full";
}

export interface BottomSheetProps {
  snap: SheetSnap;
  onSnapChange: (s: SheetSnap) => void;
  children: React.ReactNode;
  /** 右上角插槽 */
  headerRight?: React.ReactNode;
}

export function BottomSheet({
  snap,
  onSnapChange,
  children,
  headerRight,
}: BottomSheetProps) {
  const sheetRef   = useRef<HTMLDivElement>(null);
  const handleRef  = useRef<HTMLDivElement>(null);

  // 拖拽状态
  const dragStart  = useRef<{ y: number; snapVH: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const [liveH, setLiveH]       = useState<number | null>(null);

  const vh = useRef(window.innerHeight);
  useEffect(() => {
    const update = () => { vh.current = window.innerHeight; };
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  // 触摸开始
  const onTouchStart = useCallback((e: React.TouchEvent) => {
    const touch = e.touches[0];
    dragStart.current = { y: touch.clientY, snapVH: SNAP_VH[snap] };
    setDragging(true);
  }, [snap]);

  // 触摸移动
  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (!dragStart.current) return;
    const dy = dragStart.current.y - e.touches[0].clientY;
    const newRatio = Math.min(0.95, Math.max(0.08, dragStart.current.snapVH + dy / vh.current));
    setLiveH(newRatio * vh.current);
  }, []);

  // 触摸结束 → 吸附到最近档位
  const onTouchEnd = useCallback((e: React.TouchEvent) => {
    if (!dragStart.current) return;
    const dy = dragStart.current.y - e.changedTouches[0].clientY;
    const newRatio = Math.min(0.95, Math.max(0.08, dragStart.current.snapVH + dy / vh.current));
    dragStart.current = null;
    setDragging(false);
    setLiveH(null);
    onSnapChange(snapFromVH(newRatio));
  }, [onSnapChange]);

  // 鼠标拖拽（桌面调试用）
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    dragStart.current = { y: e.clientY, snapVH: SNAP_VH[snap] };
    setDragging(true);

    const onMouseMove = (ev: MouseEvent) => {
      if (!dragStart.current) return;
      const dy = dragStart.current.y - ev.clientY;
      const newRatio = Math.min(0.95, Math.max(0.08, dragStart.current.snapVH + dy / vh.current));
      setLiveH(newRatio * vh.current);
    };
    const onMouseUp = (ev: MouseEvent) => {
      if (!dragStart.current) return;
      const dy = dragStart.current.y - ev.clientY;
      const newRatio = Math.min(0.95, Math.max(0.08, dragStart.current.snapVH + dy / vh.current));
      dragStart.current = null;
      setDragging(false);
      setLiveH(null);
      onSnapChange(snapFromVH(newRatio));
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, [snap, onSnapChange]);

  // 点击手柄 → 在 peek ⟺ half 之间切换（full 由拖拽触达，点击不进入 full）
  const onHandleClick = useCallback(() => {
    if (dragging) return;
    // 当前是 full 时，点击收回到 half；否则 peek ⟺ half
    const next: Record<SheetSnap, SheetSnap> = { peek: "half", half: "peek", full: "half" };
    onSnapChange(next[snap]);
  }, [snap, onSnapChange, dragging]);

  const heightPx   = liveH ?? SNAP_VH[snap] * vh.current;
  const isFullSnap = snap === "full" && !liveH;

  return (
    <div
      ref={sheetRef}
      className={`bottom-sheet${dragging ? " dragging" : ""}${isFullSnap ? " snap-full" : ""}`}
      style={{
        height: `${heightPx}px`,
        transition: dragging ? "none" : "height 0.35s cubic-bezier(0.32,0.72,0,1)",
      }}
    >
      {/* ── 拖拽手柄 ── */}
      <div
        ref={handleRef}
        className="sheet-handle-area"
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        onMouseDown={onMouseDown}
        onClick={onHandleClick}
      >
        <div className="sheet-handle-bar" />
        {headerRight && (
          <div className="sheet-header-right">{headerRight}</div>
        )}
      </div>

      {/* ── 内容区（撑满剩余高度） ── */}
      <div className="sheet-content">
        {children}
      </div>
    </div>
  );
}
