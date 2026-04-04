"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { LayoutDashboard, History, BookOpen, Settings, LogOut, TrendingUp } from "lucide-react"
import { motion } from "motion/react"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  return (
    <div className="min-h-screen flex bg-[#FAF9F6]">
      {/* Sidebar */}
      <aside className="w-64 border-r border-[#E5E5E5] bg-[#FAF9F6] flex flex-col shrink-0">
        <div className="h-16 flex items-center px-6 border-b border-[#E5E5E5]">
          <span className="text-lg font-serif italic font-medium text-[#111111]">Aura</span>
        </div>
        <nav className="flex-1 px-4 py-6 space-y-1">
          <NavItem href="/dashboard" icon={<LayoutDashboard size={18} />} label="Workspace" active={pathname === "/dashboard"} />
          <NavItem href="/dashboard/history" icon={<History size={18} />} label="History" active={pathname === "/dashboard/history"} />
          <NavItem href="/dashboard/questions" icon={<BookOpen size={18} />} label="Question Bank" active={pathname === "/dashboard/questions"} />
          <NavItem href="/dashboard/analytics" icon={<TrendingUp size={18} />} label="Analytics" active={pathname === "/dashboard/analytics"} />
        </nav>
        <div className="p-4 border-t border-[#E5E5E5]">
          <NavItem href="/dashboard/settings" icon={<Settings size={18} />} label="Settings" active={pathname === "/dashboard/settings"} />
          <NavItem href="/" icon={<LogOut size={18} />} label="Sign Out" />
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden">
        {children}
      </main>
    </div>
  )
}

function NavItem({ href, icon, label, active }: { href: string, icon: React.ReactNode, label: string, active?: boolean }) {
  return (
    <Link 
      href={href} 
      className={`relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
        active 
          ? "text-[#111111]" 
          : "text-[#666666] hover:text-[#111111]"
      }`}
    >
      {active && (
        <motion.div
          layoutId="sidebar-active-indicator"
          className="absolute inset-0 bg-[#EBE9E0] rounded-lg"
          transition={{ type: "spring", stiffness: 350, damping: 30 }}
        />
      )}
      <span className="relative z-10 flex items-center gap-3">
        {icon}
        {label}
      </span>
    </Link>
  )
}
