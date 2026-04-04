"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "motion/react"
import { Search, LayoutDashboard, History, BookOpen, Settings, LogOut, ArrowRight } from "lucide-react"
import { useRouter } from "next/navigation"

const commands = [
  { id: "dashboard", title: "Dashboard", icon: LayoutDashboard, href: "/dashboard", section: "Navigation" },
  { id: "history", title: "Interview History", icon: History, href: "/dashboard/history", section: "Navigation" },
  { id: "questions", title: "Question Bank", icon: BookOpen, href: "/dashboard/questions", section: "Navigation" },
  { id: "start", title: "Begin Simulation", icon: ArrowRight, href: "/interview/setup", section: "Actions" },
  { id: "settings", title: "Settings", icon: Settings, href: "/dashboard/settings", section: "Account" },
  { id: "logout", title: "Log out", icon: LogOut, href: "/", section: "Account" },
]

export function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false)
  const [search, setSearch] = useState("")
  const [selectedIndex, setSelectedIndex] = useState(0)
  const router = useRouter()

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setIsOpen((open) => !open)
      }
      if (e.key === "Escape") {
        setIsOpen(false)
      }
    }

    document.addEventListener("keydown", down)
    return () => document.removeEventListener("keydown", down)
  }, [])

  const filteredCommands = commands.filter((cmd) =>
    cmd.title.toLowerCase().includes(search.toLowerCase())
  )

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelectedIndex(0)
  }, [search])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return

      if (e.key === "ArrowDown") {
        e.preventDefault()
        setSelectedIndex((prev) => (prev + 1) % filteredCommands.length)
      }
      if (e.key === "ArrowUp") {
        e.preventDefault()
        setSelectedIndex((prev) => (prev - 1 + filteredCommands.length) % filteredCommands.length)
      }
      if (e.key === "Enter") {
        e.preventDefault()
        const selected = filteredCommands[selectedIndex]
        if (selected) {
          setIsOpen(false)
          router.push(selected.href)
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [isOpen, filteredCommands, selectedIndex, router])

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/20 backdrop-blur-sm"
            onClick={() => setIsOpen(false)}
          />
          <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] pointer-events-none">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -20 }}
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
              className="w-full max-w-xl bg-white rounded-2xl shadow-2xl overflow-hidden border border-[#E5E5E5] pointer-events-auto"
            >
              <div className="flex items-center px-4 py-4 border-b border-[#E5E5E5]">
                <Search className="w-5 h-5 text-[#999999] mr-3" />
                <input
                  autoFocus
                  className="flex-1 bg-transparent outline-none text-[#111111] placeholder:text-[#999999] text-lg"
                  placeholder="Type a command or search..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <div className="flex items-center gap-1 text-xs text-[#999999] font-mono bg-[#F5F5F5] px-2 py-1 rounded">
                  <span>esc</span>
                </div>
              </div>

              <div className="max-h-[60vh] overflow-y-auto p-2">
                {filteredCommands.length === 0 ? (
                  <div className="py-12 text-center text-[#666666] text-sm">
                    No results found.
                  </div>
                ) : (
                  <div className="space-y-1">
                    {filteredCommands.map((cmd, index) => {
                      const isSelected = index === selectedIndex
                      return (
                        <div
                          key={cmd.id}
                          className={`flex items-center px-4 py-3 rounded-xl cursor-pointer transition-colors ${
                            isSelected ? "bg-[#F5F5F5] text-[#111111]" : "text-[#666666] hover:bg-[#FAFAFA]"
                          }`}
                          onMouseEnter={() => setSelectedIndex(index)}
                          onClick={() => {
                            setIsOpen(false)
                            router.push(cmd.href)
                          }}
                        >
                          <cmd.icon className={`w-5 h-5 mr-3 ${isSelected ? "text-[#111111]" : "text-[#999999]"}`} />
                          <span className="font-medium">{cmd.title}</span>
                          {isSelected && (
                            <span className="ml-auto text-xs text-[#999999] font-mono">
                              ↵
                            </span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
              
              <div className="bg-[#FAFAFA] border-t border-[#E5E5E5] px-4 py-3 flex items-center justify-between text-xs text-[#999999]">
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1">
                    <kbd className="font-mono bg-[#E5E5E5] px-1.5 py-0.5 rounded text-[#666666]">↑</kbd>
                    <kbd className="font-mono bg-[#E5E5E5] px-1.5 py-0.5 rounded text-[#666666]">↓</kbd>
                    to navigate
                  </span>
                  <span className="flex items-center gap-1">
                    <kbd className="font-mono bg-[#E5E5E5] px-1.5 py-0.5 rounded text-[#666666]">↵</kbd>
                    to select
                  </span>
                </div>
                <div className="font-medium">AI Mock Interview</div>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  )
}
