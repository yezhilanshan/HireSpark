import { cn } from "@/lib/utils"
import React from "react"

export function Badge({ className, variant = "default", ...props }: React.HTMLAttributes<HTMLDivElement> & { variant?: "default" | "success" | "warning" | "neutral" }) {
  const variants = {
    default: "bg-[#F5F5F5] text-[#111111] border-[#E5E5E5]",
    success: "bg-[#EDF5F0] text-[#2E6A45] border-[#D1E5D8]",
    warning: "bg-[#FDF5E6] text-[#8C5A15] border-[#F5E1C3]",
    neutral: "bg-white text-[#666666] border-[#E5E5E5]",
  }
  return (
    <div className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium", variants[variant], className)} {...props} />
  )
}
