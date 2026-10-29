import { cn } from "@/lib/utils";

/** The KAIROS mark: a small cube drawn with 3D-transformed faces. */
export function LogoCube({ className }: { className?: string }) {
  return (
    <div className={cn("flex h-9 w-9 items-center justify-center [perspective:200px]", className)} aria-hidden>
      <div className="relative h-5 w-5 [transform-style:preserve-3d] [transform:rotateX(-24deg)_rotateY(38deg)]">
        <span className="absolute inset-0 rounded-[3px] bg-primary [transform:translateZ(10px)]" />
        <span className="absolute inset-0 rounded-[3px] bg-[hsl(250_70%_45%)] [transform:rotateY(90deg)_translateZ(10px)]" />
        <span className="absolute inset-0 rounded-[3px] bg-[hsl(var(--glow-2))] [transform:rotateX(90deg)_translateZ(10px)]" />
      </div>
    </div>
  );
}
