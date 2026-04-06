import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide",
  {
    variants: {
      variant: {
        default: "border-slate-200 bg-slate-100 text-slate-700",
        outline: "border-slate-300 bg-transparent text-slate-600",
        success: "border-emerald-200 bg-emerald-100 text-emerald-700",
        warning: "border-amber-200 bg-amber-100 text-amber-700",
        danger: "border-rose-200 bg-rose-100 text-rose-700",
        info: "border-sky-200 bg-sky-100 text-sky-700",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge }
