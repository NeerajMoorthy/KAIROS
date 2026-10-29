import { useRef, type HTMLAttributes, type PointerEvent } from "react";
import { cn } from "@/lib/utils";

/**
 * Tilts its content in 3D toward the mouse pointer, with a soft glare.
 *
 * The angle is written straight to CSS variables on the element, so moving the
 * mouse never re-renders React. Touch and pen input are ignored (a card that
 * tilts under a scrolling finger is distracting), and `prefers-reduced-motion`
 * turns the effect off in index.css.
 */
export function Tilt({
  max = 5,
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & { max?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  function move(e: PointerEvent<HTMLDivElement>) {
    const el = ref.current;
    if (!el || e.pointerType !== "mouse") return;
    const box = el.getBoundingClientRect();
    const x = (e.clientX - box.left) / box.width;
    const y = (e.clientY - box.top) / box.height;
    el.style.setProperty("--rx", `${(0.5 - y) * max}deg`);
    el.style.setProperty("--ry", `${(x - 0.5) * max}deg`);
    el.style.setProperty("--gx", `${x * 100}%`);
    el.style.setProperty("--gy", `${y * 100}%`);
    el.dataset.active = "true";
  }

  function reset() {
    const el = ref.current;
    if (!el) return;
    el.style.setProperty("--rx", "0deg");
    el.style.setProperty("--ry", "0deg");
    el.dataset.active = "false";
  }

  return (
    <div
      ref={ref}
      className={cn("tilt rounded-xl", className)}
      onPointerMove={move}
      onPointerLeave={reset}
      {...props}
    >
      {children}
      <span className="tilt-glare" aria-hidden />
    </div>
  );
}
