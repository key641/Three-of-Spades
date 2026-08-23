import { useState } from "react";
import { Plus, Settings, Trash2, Check, Edit2, Pencil, User, Route, Clock, ChevronRight } from "lucide-react";
import type { OnboardingProfile } from "../hooks/useOnboarding";
import type { HistoryTrip } from "../App";

export interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  profile: OnboardingProfile;
  trips: HistoryTrip[];
  activeTripId?: string | null;
  onNewTrip: () => void;
  onSelectTrip: (trip: HistoryTrip) => void;
  onOpenSettings: () => void;
  onRenameTrip: (tripId: string, newTitle: string) => void;
  onDeleteTrip: (tripId: string) => void;
}

export function Sidebar({
  isOpen,
  onClose,
  profile,
  trips,
  activeTripId,
  onNewTrip,
  onSelectTrip,
  onOpenSettings,
  onRenameTrip,
  onDeleteTrip,
}: SidebarProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<HistoryTrip | null>(null);

  function handleStartRename(trip: HistoryTrip, e: React.MouseEvent) {
    e.stopPropagation();
    setEditingId(trip.id);
    setEditingTitle(trip.title);
  }

  function handleSaveRename(tripId: string, e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (editingTitle.trim()) {
      onRenameTrip(tripId, editingTitle.trim());
    }
    setEditingId(null);
  }

  function handleDelete(trip: HistoryTrip, e: React.MouseEvent) {
    e.stopPropagation();
    setDeleteTarget(trip);
  }

  function confirmDelete() {
    if (deleteTarget) {
      onDeleteTrip(deleteTarget.id);
      setDeleteTarget(null);
    }
  }

  function cancelDelete() {
    setDeleteTarget(null);
  }

  return (
    <>
      {/* ── 侧边栏抽屉 ── */}
      <aside className="sidebar-drawer" aria-label="侧边栏">
        {/* 顶部用户信息与设置 */}
        <div className="sidebar-user-header">
          <div
            className="sidebar-user-info"
            onClick={() => {
              onClose();
              onOpenSettings();
            }}
          >
            <div className="sidebar-user-avatar">
              <User size={18} strokeWidth={2} style={{ color: "var(--color-primary-dark)" }} />
            </div>
            <div className="sidebar-user-name">Andy</div>
          </div>

          <button
            type="button"
            className="sidebar-settings-btn"
            onClick={() => {
              onClose();
              onOpenSettings();
            }}
            title="出行偏好设置"
            aria-label="设置"
          >
            <Settings size={18} strokeWidth={1.75} />
          </button>
        </div>

        {/* 我的行程列表区 */}
        <div className="sidebar-trips-section">
          <div className="sidebar-section-header">
            <h3 className="sidebar-section-title">我的行程</h3>
            {trips.length > 0 && (
              <button
                type="button"
                className="sidebar-edit-btn"
                onClick={() => {
                  setIsEditing(!isEditing);
                  setEditingId(null);
                }}
                title={isEditing ? "完成" : "编辑"}
                aria-label={isEditing ? "完成" : "编辑"}
              >
                <Pencil size={14} strokeWidth={2} />
              </button>
            )}
          </div>

          {/* 新建行程按钮 */}
          <button
            type="button"
            className="sidebar-new-btn"
            onClick={() => {
              onClose();
              onNewTrip();
            }}
          >
            <Plus size={18} strokeWidth={2.2} />
            <span>新建行程</span>
          </button>

          {trips.length === 0 ? (
            <div className="sidebar-empty-hint">
              还没有规划过的行程<br />
              点击上方「新建行程」开始探索
            </div>
          ) : (
            <div className="sidebar-trips-list">
              {trips.map((trip) => {
                const isActive = trip.id === activeTripId;
                const isItemEditing = isEditing && editingId === trip.id;

                return (
                  <div
                    key={trip.id}
                    className={`sidebar-trip-card${isActive ? " active-trip" : ""}`}
                    onClick={() => {
                      if (!isEditing) {
                        onClose();
                        onSelectTrip(trip);
                      }
                    }}
                  >
                    {isItemEditing ? (
                      <div className="sidebar-trip-item-row">
                        <form
                          className="sidebar-trip-edit-row"
                          onSubmit={(e) => handleSaveRename(trip.id, e)}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="text"
                            className="sidebar-trip-rename-input"
                            value={editingTitle}
                            onChange={(e) => setEditingTitle(e.target.value)}
                            autoFocus
                            onBlur={() => handleSaveRename(trip.id)}
                          />
                        </form>
                        <div className="sidebar-trip-actions">
                          <button
                            type="button"
                            className="sidebar-trip-action-btn rename"
                            onClick={(e) => { e.stopPropagation(); handleSaveRename(trip.id, e); }}
                            title="确认"
                          >
                            <Check size={14} strokeWidth={2} />
                          </button>
                          <button
                            type="button"
                            className="sidebar-trip-action-btn delete"
                            onClick={(e) => handleDelete(trip, e)}
                            title="删除"
                          >
                            <Trash2 size={13} strokeWidth={2} />
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="sidebar-trip-item-row">
                        <div className="sidebar-trip-title">{trip.title}</div>
                        {isEditing && (
                          <div className="sidebar-trip-actions">
                            <button
                              type="button"
                              className="sidebar-trip-action-btn rename"
                              onClick={(e) => handleStartRename(trip, e)}
                              title="重命名"
                            >
                              <Pencil size={13} strokeWidth={2} />
                            </button>
                            <button
                              type="button"
                              className="sidebar-trip-action-btn delete"
                              onClick={(e) => handleDelete(trip, e)}
                              title="删除"
                            >
                              <Trash2 size={13} strokeWidth={2} />
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </aside>

      {/* 删除确认弹窗 */}
      {deleteTarget && (
        <div className="sidebar-delete-overlay" onClick={cancelDelete}>
          <div className="sidebar-delete-modal" onClick={(e) => e.stopPropagation()}>
            <h4 className="sidebar-delete-title">删除行程</h4>
            <p className="sidebar-delete-content">
              确认删除「{deleteTarget.title}」行程？该操作不可恢复。
            </p>
            <div className="sidebar-delete-actions">
              <button type="button" className="sidebar-delete-cancel" onClick={cancelDelete}>
                取消
              </button>
              <button type="button" className="sidebar-delete-confirm" onClick={confirmDelete}>
                删除
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
