import { useState } from "react";
import { Home, Plus, User, MapPin, Download } from "lucide-react";

export type AppTab = "home" | "plan" | "profile";
export type PlanAction = "new_trip" | "import_route";

export interface TabBarProps {
  active: AppTab;
  onChange: (tab: AppTab) => void;
  onPlanAction?: (action: PlanAction) => void;
  hasNewRoute?: boolean;
}

export function TabBar({ active, onChange, onPlanAction, hasNewRoute }: TabBarProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  function handlePlusClick() {
    setMenuOpen((prev) => !prev);
  }

  function handleAction(action: PlanAction) {
    setMenuOpen(false);
    if (action === "new_trip") {
      onChange("plan");
    }
    onPlanAction?.(action);
  }

  function handleOverlayClick() {
    setMenuOpen(false);
  }

  return (
    <>
      {/* 半透明遮罩 */}
      {menuOpen && (
        <div
          className="tab-bar-overlay"
          onClick={handleOverlayClick}
          aria-hidden="true"
        />
      )}

      {/* 弹出按钮组 */}
      {menuOpen && (
        <div className="tab-bar-action-menu">
          <button
            type="button"
            className="tab-bar-action-btn"
            onClick={() => handleAction("import_route")}
          >
            <span className="tab-bar-action-icon tab-bar-action-icon--import">
              <Download size={18} />
            </span>
            <span className="tab-bar-action-label">
              <span className="tab-bar-action-title">导入推荐行程</span>
              <span className="tab-bar-action-desc">从精选路线一键导入</span>
            </span>
          </button>

          <button
            type="button"
            className="tab-bar-action-btn"
            onClick={() => handleAction("new_trip")}
          >
            <span className="tab-bar-action-icon tab-bar-action-icon--new">
              <MapPin size={18} />
            </span>
            <span className="tab-bar-action-label">
              <span className="tab-bar-action-title">创建今日行程</span>
              <span className="tab-bar-action-desc">AI 帮你规划当日路线</span>
            </span>
          </button>
        </div>
      )}

      {/* Tab Bar 本体 */}
      <nav className="tab-bar">
        {/* 发现 */}
        <button
          type="button"
          className={`tab-bar-item${active === "home" ? " active" : ""}`}
          onClick={() => { setMenuOpen(false); onChange("home"); }}
        >
          <span className="tab-bar-icon"><Home size={20} /></span>
          <span className="tab-bar-label">发现</span>
        </button>

        {/* 中间 + / × 按钮 */}
        <button
          type="button"
          className={`tab-bar-item tab-bar-item--plan${menuOpen ? " plan-open" : ""}`}
          onClick={handlePlusClick}
          aria-label={menuOpen ? "关闭菜单" : "新建行程"}
        >
          <span className={`tab-bar-icon tab-bar-icon--plan${menuOpen ? " rotated" : ""}`}>
            <Plus size={22} />
            {!menuOpen && hasNewRoute && <span className="tab-bar-dot" />}
          </span>
        </button>

        {/* 我的 */}
        <button
          type="button"
          className={`tab-bar-item${active === "profile" ? " active" : ""}`}
          onClick={() => { setMenuOpen(false); onChange("profile"); }}
        >
          <span className="tab-bar-icon"><User size={20} /></span>
          <span className="tab-bar-label">我的</span>
        </button>
      </nav>
    </>
  );
}
