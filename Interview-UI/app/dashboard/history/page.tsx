"use client"

import { useState, useMemo } from "react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ArrowRight, Search, Filter, Calendar } from "lucide-react"
import Link from "next/link"
import { motion, AnimatePresence, Variants } from "motion/react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"

const historyData = [
  { id: 1, title: "Behavioral: Conflict Resolution", role: "Product Manager", date: "Oct 14, 2026", score: 85, duration: "15m", tags: ["Behavioral", "Leadership"] },
  { id: 2, title: "Product Sense: Design a Vending Machine", role: "Product Manager", date: "Oct 12, 2026", score: 78, duration: "25m", tags: ["Product Sense", "Design"] },
  { id: 3, title: "Execution: Metric Decline", role: "Product Manager", date: "Oct 10, 2026", score: 88, duration: "20m", tags: ["Execution", "Analytics"] },
  { id: 4, title: "Technical: API Design for Messaging", role: "Technical PM", date: "Oct 05, 2026", score: 92, duration: "30m", tags: ["System Design", "Technical"] },
  { id: 5, title: "Behavioral: Failure & Learnings", role: "Product Manager", date: "Sep 28, 2026", score: 81, duration: "12m", tags: ["Behavioral"] },
  { id: 6, title: "Strategy: Entering a New Market", role: "Product Manager", date: "Sep 25, 2026", score: 74, duration: "35m", tags: ["Strategy", "GTM"] },
]

const chartData = [...historyData].reverse().map(item => ({
  name: item.date.split(",")[0],
  score: item.score
}))

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.05 }
  }
}

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 30 } }
}

export default function HistoryPage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [isFilterActive, setIsFilterActive] = useState(false)

  const filteredData = useMemo(() => {
    return historyData.filter(item => 
      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))
    )
  }, [searchQuery])

  return (
    <div className="flex-1 overflow-y-auto p-8 lg:p-12">
      <motion.div 
        className="max-w-5xl mx-auto space-y-10"
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        
        {/* Header */}
        <motion.header variants={itemVariants} className="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div>
            <h1 className="text-3xl font-serif text-[#111111] tracking-tight">Interview History</h1>
            <p className="text-[#666666] mt-2">Review your past performances and track your progress over time.</p>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="relative group">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[#999999] group-focus-within:text-[#111111] transition-colors" size={16} />
              <input 
                type="text" 
                placeholder="Search sessions or tags..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-10 pl-9 pr-4 rounded-lg border border-[#E5E5E5] bg-white text-sm focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] transition-all w-full md:w-64"
              />
            </div>
            <button 
              onClick={() => setIsFilterActive(!isFilterActive)}
              className={`h-10 px-3 flex items-center gap-2 rounded-lg border text-sm font-medium transition-colors shrink-0 ${
                isFilterActive 
                  ? "bg-[#111111] text-white border-[#111111]" 
                  : "bg-white text-[#111111] border-[#E5E5E5] hover:bg-[#F5F5F5]"
              }`}
            >
              <Filter size={16} />
              Filter
            </button>
          </div>
        </motion.header>

        {/* Chart Section */}
        <motion.div variants={itemVariants}>
          <Card className="p-6 bg-white border-[#E5E5E5] hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] transition-shadow duration-300">
            <div className="flex items-center gap-2 mb-6">
              <Calendar size={16} className="text-[#666666]" />
              <h3 className="text-sm font-medium text-[#111111]">Performance Trend</h3>
            </div>
            <div className="h-[200px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F5F5F5" />
                  <XAxis 
                    dataKey="name" 
                    axisLine={false} 
                    tickLine={false} 
                    tick={{ fontSize: 12, fill: '#999999' }} 
                    dy={10}
                  />
                  <YAxis 
                    axisLine={false} 
                    tickLine={false} 
                    tick={{ fontSize: 12, fill: '#999999' }} 
                    domain={['dataMin - 10', 100]}
                  />
                  <Tooltip 
                    contentStyle={{ borderRadius: '8px', border: '1px solid #E5E5E5', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}
                    itemStyle={{ color: '#111111', fontWeight: 500 }}
                    cursor={{ stroke: '#E5E5E5', strokeWidth: 1, strokeDasharray: '3 3' }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="score" 
                    stroke="#111111" 
                    strokeWidth={2} 
                    dot={{ r: 4, fill: '#111111', strokeWidth: 0 }} 
                    activeDot={{ r: 6, fill: '#111111', stroke: '#fff', strokeWidth: 2 }}
                    animationDuration={1500}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </motion.div>

        {/* List */}
        <motion.div variants={itemVariants} className="space-y-4" layout>
          <AnimatePresence mode="popLayout">
            {filteredData.length > 0 ? (
              filteredData.map((item) => (
                <motion.div
                  key={item.id}
                  layout
                  initial={{ opacity: 0, scale: 0.98, y: 10 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.98, y: -10 }}
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                >
                  <Link href={`/dashboard/history/${item.id}`} className="block group">
                    <Card className="p-6 flex flex-col md:flex-row md:items-center justify-between gap-6 hover:border-[#111111] hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] transition-all duration-300">
                      <div className="flex-1 space-y-3">
                        <div className="flex items-center gap-3">
                          <h3 className="text-lg font-medium text-[#111111] group-hover:underline decoration-[#E5E5E5] underline-offset-4">
                            {item.title}
                          </h3>
                          <div className="hidden md:flex gap-2">
                            {item.tags.map(tag => (
                              <Badge key={tag} variant="neutral">{tag}</Badge>
                            ))}
                          </div>
                        </div>
                        <div className="flex items-center gap-4 text-sm text-[#666666]">
                          <span>{item.date}</span>
                          <span className="w-1 h-1 rounded-full bg-[#D4D1C1]" />
                          <span>{item.role}</span>
                          <span className="w-1 h-1 rounded-full bg-[#D4D1C1]" />
                          <span>{item.duration}</span>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-8 md:shrink-0 border-t md:border-t-0 border-[#E5E5E5] pt-4 md:pt-0">
                        <div className="text-right">
                          <div className="text-2xl font-serif text-[#111111]">{item.score}</div>
                          <div className="text-xs text-[#999999] uppercase tracking-wider mt-1">Score</div>
                        </div>
                        <div className="w-10 h-10 rounded-full border border-[#E5E5E5] flex items-center justify-center text-[#111111] group-hover:bg-[#111111] group-hover:text-white transition-colors duration-300">
                          <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
                        </div>
                      </div>
                    </Card>
                  </Link>
                </motion.div>
              ))
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="py-12 text-center text-[#666666]"
              >
                No sessions found matching &quot;{searchQuery}&quot;
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

      </motion.div>
    </div>
  )
}
