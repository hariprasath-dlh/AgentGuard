import { cva, type VariantProps } from "class-variance-authority";
import {
  forwardRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

export const btn = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-display text-sm font-medium transition-all duration-300 ease-[var(--ease-premium)] disabled:pointer-events-none disabled:opacity-50 min-h-10 cursor-pointer",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-foreground hover:bg-primary-deep",
        dark: "bg-brown-dark text-brown-foreground hover:bg-brown",
        outline:
          "border border-foreground/30 text-foreground hover:border-foreground hover:bg-foreground hover:text-background",
        ghost: "text-foreground hover:bg-secondary",
        teal: "bg-teal text-teal-foreground hover:brightness-95",
        allow: "bg-allow text-ivory hover:brightness-110",
        deny: "bg-deny text-ivory hover:brightness-110",
        light:
          "border border-brown-foreground/40 text-brown-foreground hover:bg-brown-foreground hover:text-brown-dark",
      },
      size: { sm: "px-3 py-1.5 text-xs min-h-8", md: "px-5 py-2.5", lg: "px-7 py-3.5 text-base" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof btn>
>(({ className, variant, size, ...p }, ref) => (
  <button ref={ref} className={cn(btn({ variant, size }), className)} {...p} />
));
Button.displayName = "Button";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...p }, ref) => (
    <input
      ref={ref}
      className={cn(
        "w-full border-0 border-b border-border bg-transparent px-0 py-2.5 text-base text-foreground placeholder:text-muted-foreground/70 focus:border-primary focus:outline-none focus-visible:outline-none transition-colors",
        className,
      )}
      {...p}
    />
  ),
);
Input.displayName = "Input";

export function Field({
  label,
  htmlFor,
  children,
  error,
}: {
  label: string;
  htmlFor: string;
  children: ReactNode;
  error?: string;
}) {
  return (
    <div className="space-y-1">
      <label htmlFor={htmlFor} className="eyebrow text-muted-foreground">
        {label}
      </label>
      {children}
      {error && <p className="text-xs text-deny">{error}</p>}
    </div>
  );
}

const tones: Record<string, string> = {
  ALLOW: "text-allow border-allow/40 bg-allow/10",
  APPROVED: "text-allow border-allow/40 bg-allow/10",
  ACTIVE: "text-allow border-allow/40 bg-allow/10",
  DENY: "text-deny border-deny/40 bg-deny/10",
  DENIED: "text-deny border-deny/40 bg-deny/10",
  SUSPENDED: "text-deny border-deny/40 bg-deny/10",
  CRITICAL: "text-deny border-deny/40 bg-deny/10",
  PENDING: "text-pending border-pending/40 bg-pending/10",
  "PENDING · AWAITING REVIEW": "text-pending border-pending/40 bg-pending/10",
  HIGH: "text-pending border-pending/40 bg-pending/10",
  "HIGH RISK": "text-pending border-pending/40 bg-pending/10",
  MEDIUM: "text-info border-info/40 bg-info/10",
  LOW: "text-allow border-allow/40 bg-allow/10",
  EXPIRED: "text-muted-foreground border-border bg-muted",
  RETIRED: "text-muted-foreground border-border bg-muted",
  INACTIVE: "text-muted-foreground border-border bg-muted",
};

export function Tag({ v, className }: { v: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center border px-2 py-0.5 font-display text-[0.65rem] font-semibold tracking-[0.12em]",
        tones[v] ?? "border-border text-muted-foreground",
        className,
      )}
    >
      {v}
    </span>
  );
}

export function Panel({
  title,
  num,
  action,
  children,
  className,
}: {
  title?: string;
  num?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("border border-border bg-ivory", className)}>
      {title && (
        <header className="flex items-center justify-between gap-3 border-b border-border px-5 py-3">
          <h2 className="eyebrow text-foreground">
            {num && <span className="mr-2 text-primary">{num}</span>}
            {title}
          </h2>
          {action}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function Confirm({
  trigger,
  title,
  description,
  confirmLabel = "Confirm",
  onConfirm,
}: {
  trigger: ReactNode;
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger>
      <AlertDialogContent className="rounded-none border-border bg-ivory">
        <AlertDialogHeader>
          <AlertDialogTitle className="font-serif-display text-3xl">{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel className={cn(btn({ variant: "outline" }), "rounded-none")}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            className={cn(btn({ variant: "deny" }), "rounded-none")}
            onClick={onConfirm}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <Button
      variant="ghost"
      size="sm"
      aria-label={label}
      onClick={async () => {
        await navigator.clipboard?.writeText(value).catch(() => undefined);
        setDone(true);
        toast.success("Copied to clipboard");
        setTimeout(() => setDone(false), 1500);
      }}
    >
      {done ? <Check className="h-3.5 w-3.5 text-allow" /> : <Copy className="h-3.5 w-3.5" />}
      {label}
    </Button>
  );
}

export function PageHead({
  num,
  title,
  lede,
  action,
}: {
  num: string;
  title: string;
  lede: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 border-b border-border pb-6 md:flex-row md:items-end md:justify-between">
      <div>
        <p className="eyebrow text-primary">{num}</p>
        <h1 className="mt-2 font-serif-display text-5xl md:text-6xl">{title}</h1>
        <p className="mt-3 max-w-xl text-muted-foreground">{lede}</p>
      </div>
      {action}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="border border-dashed border-border p-10 text-center text-muted-foreground">
      {children}
    </div>
  );
}

export function Json({ data }: { data: unknown }) {
  return (
    <pre className="mono max-h-72 overflow-auto bg-brown-dark p-4 text-xs leading-relaxed text-brown-foreground">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

export const selectCls =
  "w-full border-0 border-b border-border bg-transparent py-2.5 text-base text-foreground focus:border-primary focus:outline-none";
export const textareaCls =
  "mono w-full border border-border bg-background p-3 text-xs text-foreground focus:border-primary focus:outline-none";
