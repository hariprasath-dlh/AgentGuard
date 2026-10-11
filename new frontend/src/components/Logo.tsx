import { type CSSProperties } from "react";
import { cn } from "@/lib/utils";
import logoImg from "@/assets/logo.png";

export function LogoMark({ className }: { className?: string }) {
  return (
    <img
      src={logoImg}
      alt="AgentGuard logo"
      className={cn("h-8 w-8 object-contain rounded-md select-none", className)}
      draggable={false}
    />
  );
}

export function Logo({
  tone = "dark",
  className,
  textClassName,
  textStyle,
}: {
  tone?: "dark" | "light";
  className?: string;
  textClassName?: string;
  textStyle?: CSSProperties;
}) {
  return (
    <div
      className={cn("inline-flex items-center gap-2.5 select-none", className)}
      aria-label="AgentGuard"
    >
      <LogoMark />
      <span
        style={textStyle}
        className={cn(
          "font-display text-lg font-semibold tracking-tight",
          tone === "light" ? "text-brown-foreground" : "text-foreground",
          textClassName,
        )}
      >
        AgentGuard
      </span>
    </div>
  );
}
