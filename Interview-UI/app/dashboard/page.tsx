"use client"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ArrowRight, Play, TrendingUp, Clock, Target } from "lucide-react"
import Link from "next/link"
import { motion, Variants } from "motion/react"

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
}

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 30 } }
}

export default function DashboardPage() {
  return (
    <div className="flex-1 overflow-y-auto p-8 lg:p-12">
      <motion.div 
        className="max-w-5xl mx-auto space-y-12"
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        
        {/* Header */}
        <motion.header variants={itemVariants} className="flex items-end justify-between">
          <div>
            <h1 className="text-3xl font-serif text-[#111111] tracking-tight">Good morning, Alex.</h1>
            <p className="text-[#666666] mt-2">Ready to refine your interview skills today?</p>
          </div>
          <div className="flex items-center gap-6">
            <div className="hidden md:flex items-center gap-2 text-xs text-[#999999] bg-white border border-[#E5E5E5] px-3 py-1.5 rounded-full shadow-sm">
              <span className="font-medium">Press</span>
              <kbd className="font-mono bg-[#F5F5F5] px-1.5 py-0.5 rounded text-[#111111]">⌘K</kbd>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right hidden sm:block">
                <div className="text-sm font-medium text-[#111111]">Product Manager</div>
                <div className="text-xs text-[#999999]">Target Role</div>
              </div>
              <motion.div 
                whileHover={{ scale: 1.05 }}
                className="w-10 h-10 rounded-full bg-[#EBE9E0] flex items-center justify-center text-[#111111] font-medium cursor-pointer"
              >
                A
              </motion.div>
            </div>
          </div>
        </motion.header>

        {/* Primary Action */}
        <motion.div variants={itemVariants}>
          <Card className="p-8 bg-white border-[#E5E5E5] flex flex-col md:flex-row items-start md:items-center justify-between gap-6 hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] transition-shadow duration-300">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <Badge variant="neutral">Recommended</Badge>
                <span className="text-sm text-[#666666]">Est. 30 mins</span>
              </div>
              <h2 className="text-xl font-medium text-[#111111]">Comprehensive Product Interview</h2>
              <p className="text-[#666666] text-sm max-w-lg leading-relaxed">
                A full-length simulation covering product sense, execution, and behavioral questions. Tailored to your recent performance.
              </p>
            </div>
            <Link href="/interview/setup">
              <Button size="lg" className="gap-2 shrink-0 group">
                <Play size={16} fill="currentColor" className="group-hover:scale-110 transition-transform" />
                Begin Simulation
              </Button>
            </Link>
          </Card>
        </motion.div>

        {/* Stats & History Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          
          {/* Stats */}
          <motion.div variants={itemVariants} className="col-span-1 space-y-6">
            <h3 className="text-sm font-medium text-[#999999] uppercase tracking-wider">Overview</h3>
            <Card className="p-6 space-y-6 hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] transition-shadow duration-300">
              <div>
                <div className="text-sm text-[#666666] mb-1 flex items-center gap-2"><Target size={16}/> Average Score</div>
                <div className="text-3xl font-serif text-[#111111]">82<span className="text-lg text-[#999999]">/100</span></div>
                <div className="text-xs text-[#2E6A45] mt-2 flex items-center gap-1">
                  <TrendingUp size={12} /> +4 points this week
                </div>
              </div>
              <div className="h-px bg-[#E5E5E5]" />
              <div>
                <div className="text-sm text-[#666666] mb-1 flex items-center gap-2"><Clock size={16}/> Practice Time</div>
                <div className="text-2xl font-serif text-[#111111]">4.5<span className="text-base text-[#999999] font-sans"> hrs</span></div>
              </div>
            </Card>
          </motion.div>

          {/* Recent History */}
          <motion.div variants={itemVariants} className="col-span-1 md:col-span-2 space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-[#999999] uppercase tracking-wider">Recent Sessions</h3>
              <Link href="/dashboard/history" className="text-sm text-[#666666] hover:text-[#111111] flex items-center gap-1 group">
                View all <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
              </Link>
            </div>
            <div className="space-y-3">
              {[
                { title: "Behavioral: Conflict Resolution", date: "Yesterday", score: 85, duration: "15m" },
                { title: "Product Sense: Design a Vending Machine", date: "Oct 12", score: 78, duration: "25m" },
                { title: "Execution: Metric Decline", date: "Oct 10", score: 88, duration: "20m" },
              ].map((item, i) => (
                <Link href="/dashboard/history/session-1" key={i} className="block">
                  <motion.div whileHover={{ scale: 1.01 }} transition={{ type: "spring", stiffness: 400, damping: 30 }}>
                    <Card className="p-4 flex items-center justify-between hover:border-[#111111] transition-colors cursor-pointer group">
                      <div>
                        <div className="font-medium text-[#111111] group-hover:underline decoration-[#E5E5E5] underline-offset-4">{item.title}</div>
                        <div className="text-xs text-[#666666] mt-1">{item.date} • {item.duration}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-serif text-[#111111]">{item.score}</div>
                        <div className="text-xs text-[#999999]">Score</div>
                      </div>
                    </Card>
                  </motion.div>
                </Link>
              ))}
            </div>
          </motion.div>

        </div>
      </motion.div>
    </div>
  )
}
