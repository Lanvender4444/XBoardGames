// 包豪斯共享组件：几何形状基元 + 面板 + 按钮 + 区段标题。
// 全部为纯展示组件，无业务逻辑，供四个 feature 视图复用。
import React from "react";

type Color = "red" | "blue" | "yellow" | "black" | "white" | "paper";

const COLORS: Record<Color, string> = {
  red: "var(--bh-red)",
  blue: "var(--bh-blue)",
  yellow: "var(--bh-yellow)",
  black: "var(--bh-black)",
  white: "var(--bh-white)",
  paper: "var(--bh-paper)",
};

/** 几何形状：圆 / 方 / 三角 / 半圆 */
export function Shape({
  kind,
  size = 32,
  color = "black",
  style,
}: {
  kind: "circle" | "square" | "triangle" | "half-circle";
  size?: number;
  color?: Color;
  style?: React.CSSProperties;
}): React.ReactElement {
  if (kind === "triangle") {
    return (
      <span
        className="bh-shape bh-triangle"
        style={{ ["--w" as string]: `${size / 2}px`, ["--h" as string]: `${size}px`, ["--c" as string]: COLORS[color], ...style }}
      />
    );
  }
  const cls =
    kind === "circle" ? "bh-circle" : kind === "half-circle" ? "bh-half-circle" : "bh-square";
  return (
    <span
      className={`bh-shape ${cls}`}
      style={{ width: size, height: kind === "half-circle" ? size / 2 : size, background: COLORS[color], ...style }}
    />
  );
}

/** 白底粗黑边 + 投影面板 */
export function Panel({
  children,
  flat,
  corner,
  style,
}: {
  children: React.ReactNode;
  flat?: boolean;
  corner?: boolean;
  style?: React.CSSProperties;
}): React.ReactElement {
  return (
    <div className={`bh-panel ${flat ? "bh-panel--flat" : ""} ${corner ? "bh-corner" : ""}`} style={style}>
      {children}
    </div>
  );
}

/** 几何按钮 */
export function Button({
  children,
  variant = "yellow",
  onClick,
  disabled,
  style,
}: {
  children: React.ReactNode;
  variant?: "yellow" | "red" | "blue" | "ghost";
  onClick?: () => void;
  disabled?: boolean;
  style?: React.CSSProperties;
}): React.ReactElement {
  const cls =
    variant === "red"
      ? "bh-btn bh-btn--red"
      : variant === "blue"
        ? "bh-btn bh-btn--blue"
        : variant === "ghost"
          ? "bh-btn bh-btn--ghost"
          : "bh-btn";
  return (
    <button className={cls} onClick={onClick} disabled={disabled} style={style}>
      {children}
    </button>
  );
}

/** 区段标题：彩色圆点 + 大写标题 */
export function SectionHead({
  title,
  dot = "red",
}: {
  title: string;
  dot?: Color;
}): React.ReactElement {
  return (
    <div className="bh-section-head">
      <span className="dot bh-circle" style={{ background: COLORS[dot] }} />
      <h2>{title}</h2>
    </div>
  );
}

/** 大写小标签 */
export function Label({ children }: { children: React.ReactNode }): React.ReactElement {
  return <span className="bh-mono-label">{children}</span>;
}

/** 标签筹码 */
export function Chip({
  children,
  color = "white",
}: {
  children: React.ReactNode;
  color?: Color;
}): React.ReactElement {
  const dark = color === "black" || color === "red" || color === "blue";
  return (
    <span className="bh-chip" style={{ background: COLORS[color], color: dark ? "var(--bh-white)" : "var(--bh-black)" }}>
      {children}
    </span>
  );
}
