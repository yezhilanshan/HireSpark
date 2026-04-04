import { cn } from "@/lib/utils"
import React from "react"

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost";
  size?: "sm" | "md" | "lg";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    const variants = {
      primary: "bg-[#111111] text-white hover:bg-[#222222] shadow-sm",
      secondary: "bg-[#EBE9E0] text-[#111111] hover:bg-[#D4D1C1]",
      outline: "border border-[#E5E5E5] bg-transparent hover:bg-[#F5F5F5] text-[#111111]",
      ghost: "bg-transparent hover:bg-[#F5F5F5] text-[#666666] hover:text-[#111111]",
    }
    const sizes = {
      sm: "h-8 px-3 text-xs",
      md: "h-10 px-4 text-sm",
      lg: "h-12 px-6 text-base",
    }
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-lg font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#111111] disabled:pointer-events-none disabled:opacity-50",
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"
