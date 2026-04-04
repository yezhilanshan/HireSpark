import { cn } from "@/lib/utils"
import React from "react"

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("rounded-2xl border border-[#E5E5E5] bg-white shadow-[0_2px_8px_rgba(0,0,0,0.02)]", className)} {...props} />
  )
}
