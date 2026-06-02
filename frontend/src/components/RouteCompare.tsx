import { useEffect, useRef, useState } from "react";
import type { Route } from "../api/types";
import { RouteCard } from "./RouteCard";

export interface RouteCompareProps {
  routes: Route[];
  loading?: boolean;
  /** 从 ActionBar 冒泡上来的操作，RouteCompare 透传给 RouteCard */
  onAction?: (actionKey: string, routeId: string) => void;
}

function RouteCardSkeleton() {
  return (
    <div className="route-card skeleton">
      <div className="route-card-header" style={{ marginBottom: 12 }}>
        <div style={{ flex: 1 }}>
          <div className="sk-line sk-title" />
          <div className="sk-line sk-short" />
        </div>
        <div style={{ width: 44, height: 44, borderRadius: 8, background: "#eee" }} />
      </div>
      <div className="sk-metrics">
        <div className="sk-chip" /><div className="sk-chip" /><div className="sk-chip" />
      </div>
      <div style={{ marginTop: 12 }}>
        <div className="sk-stop" />
        <div className="sk-stop" />
        <div className="sk-stop" />
      </div>
    </div>
  );
}

export function RouteCompare({ routes, loading = false, onAction }: RouteCompareProps) {
  const swiperRef = useRef<HTMLDivElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [visibleRouteIds, setVisibleRouteIds] = useState<string[]>([]);
  const routeIdSignature = routes.map((route) => route.route_id).join("|");

  useEffect(() => {
    if (routes.length === 0) {
      setVisibleRouteIds([]);
      return;
    }
    setVisibleRouteIds((prev) => {
      const currentIds = new Set(routes.map((route) => route.route_id));
      const kept = prev.filter((routeId) => currentIds.has(routeId));
      return kept.length > 0 ? kept : [routes[0].route_id];
    });
  }, [routeIdSignature, routes]);

  useEffect(() => {
    if (routes.length <= 1) return;
    const timer = window.setInterval(() => {
      setVisibleRouteIds((prev) => {
        const currentIds = new Set(routes.map((route) => route.route_id));
        const kept = prev.filter((routeId) => currentIds.has(routeId));
        const nextRoute = routes.find((route) => !kept.includes(route.route_id));
        if (!nextRoute) {
          window.clearInterval(timer);
          return kept;
        }
        return [...kept, nextRoute.route_id];
      });
    }, 900);
    return () => window.clearInterval(timer);
  }, [routeIdSignature, routes]);

  const visibleRoutes = routes.filter((route) => visibleRouteIds.includes(route.route_id));

  useEffect(() => {
    const el = swiperRef.current;
    if (!el) return;
    const handleScroll = () => {
      const slideWidth = el.scrollWidth / (visibleRoutes.length || 1);
      const index = Math.round(el.scrollLeft / slideWidth);
      setActiveIndex(index);
    };
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, [visibleRoutes.length]);

  const showSkeletons = loading && visibleRoutes.length === 0;
  const showRoutes = visibleRoutes.length > 0;
  const routeCountText = showRoutes
    ? visibleRoutes.length < routes.length
      ? `（已生成 ${visibleRoutes.length} / ${routes.length} 条）`
      : `（${visibleRoutes.length} 条）`
    : "";

  return (
    <section className="route-section">
      <h2>规划方案 {routeCountText}</h2>

      <div className="route-swiper" ref={swiperRef}>
        {showSkeletons && (
          <>
            <div className="route-slide"><RouteCardSkeleton /></div>
            <div className="route-slide"><RouteCardSkeleton /></div>
            <div className="route-slide"><RouteCardSkeleton /></div>
          </>
        )}
        {showRoutes && visibleRoutes.map((route) => (
          <div className="route-slide" key={route.route_id}>
            <RouteCard route={route} onAction={onAction} />
          </div>
        ))}
      </div>

      {showRoutes && visibleRoutes.length > 1 && (
        <div className="swiper-dots">
          {visibleRoutes.map((_, i) => (
            <span
              key={i}
              className={`dot${i === activeIndex ? " active" : ""}`}
              onClick={() => {
                const el = swiperRef.current;
                if (!el) return;
                const slideWidth = el.scrollWidth / visibleRoutes.length;
                el.scrollTo({ left: slideWidth * i, behavior: "smooth" });
              }}
            />
          ))}
        </div>
      )}
    </section>
  );
}
