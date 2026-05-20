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

  useEffect(() => {
    const el = swiperRef.current;
    if (!el) return;
    const handleScroll = () => {
      const slideWidth = el.scrollWidth / (routes.length || 1);
      const index = Math.round(el.scrollLeft / slideWidth);
      setActiveIndex(index);
    };
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, [routes.length]);

  const showSkeletons = loading && routes.length === 0;
  const showRoutes = routes.length > 0;

  return (
    <section className="route-section">
      <h2>规划方案 {showRoutes ? `（${routes.length} 条）` : ""}</h2>

      <div className="route-swiper" ref={swiperRef}>
        {showSkeletons && (
          <>
            <div className="route-slide"><RouteCardSkeleton /></div>
            <div className="route-slide"><RouteCardSkeleton /></div>
            <div className="route-slide"><RouteCardSkeleton /></div>
          </>
        )}
        {showRoutes && routes.map((route) => (
          <div className="route-slide" key={route.route_id}>
            <RouteCard route={route} onAction={onAction} />
          </div>
        ))}
      </div>

      {showRoutes && routes.length > 1 && (
        <div className="swiper-dots">
          {routes.map((_, i) => (
            <span
              key={i}
              className={`dot${i === activeIndex ? " active" : ""}`}
              onClick={() => {
                const el = swiperRef.current;
                if (!el) return;
                const slideWidth = el.scrollWidth / routes.length;
                el.scrollTo({ left: slideWidth * i, behavior: "smooth" });
              }}
            />
          ))}
        </div>
      )}
    </section>
  );
}
