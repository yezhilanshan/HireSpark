"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Play, Search, BookOpen } from "lucide-react"
import Link from "next/link"
import { motion, AnimatePresence } from "motion/react"

const questionBank = [
  { id: 1, category: "Product Sense", title: "Design a fire alarm for the deaf.", difficulty: "Hard", frequency: "High" },
  { id: 2, category: "Behavioral", title: "Tell me about a time you failed.", difficulty: "Medium", frequency: "Very High" },
  { id: 3, category: "Execution", title: "Uber's ride requests dropped by 10%. How do you investigate?", difficulty: "Hard", frequency: "High" },
  { id: 4, category: "Strategy", title: "Should Netflix enter the cloud gaming market?", difficulty: "Medium", frequency: "Medium" },
  { id: 5, category: "Product Sense", title: "Improve the airport security experience.", difficulty: "Medium", frequency: "High" },
  { id: 6, category: "Technical", title: "Explain how a URL shortener works.", difficulty: "Medium", frequency: "Low" },
  { id: 7, category: "Behavioral", title: "How do you handle a difficult stakeholder?", difficulty: "Easy", frequency: "Very High" },
  { id: 8, category: "Execution", title: "Set success metrics for Facebook Groups.", difficulty: "Medium", frequency: "High" },
]

const categories = ["All", "Product Sense", "Execution", "Behavioral", "Strategy", "Technical"]

export default function QuestionsPage() {
  const [activeCategory, setActiveCategory] = useState("All")
  const [searchQuery, setSearchQuery] = useState("")

  const filteredQuestions = questionBank.filter(q => {
    const matchesCategory = activeCategory === "All" || q.category === activeCategory
    const matchesSearch = q.title.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesCategory && matchesSearch
  })

  return (
    <div className="flex-1 overflow-y-auto p-8 lg:p-12">
      <div className="max-w-5xl mx-auto space-y-8">
        
        {/* Header */}
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <h1 className="text-3xl font-serif text-[#111111] tracking-tight">Question Bank</h1>
            <p className="text-[#666666] mt-2">Target specific skills with our curated database of PM interview questions.</p>
          </motion.div>
          
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[#999999]" size={16} />
              <input 
                type="text" 
                placeholder="Search questions..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-10 pl-9 pr-4 rounded-lg border border-[#E5E5E5] bg-white text-sm focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] transition-all w-full md:w-64"
              />
            </div>
          </motion.div>
        </header>

        {/* Categories */}
        <motion.div 
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}
          className="flex flex-wrap gap-2"
        >
          {categories.map(category => (
            <button
              key={category}
              onClick={() => setActiveCategory(category)}
              className={`px-4 py-1.5 text-sm rounded-full border transition-all duration-200 ${
                activeCategory === category 
                  ? "bg-[#111111] text-white border-[#111111]" 
                  : "bg-white text-[#666666] border-[#E5E5E5] hover:bg-[#F5F5F5] hover:text-[#111111]"
              }`}
            >
              {category}
            </button>
          ))}
        </motion.div>

        {/* Grid */}
        <motion.div layout className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <AnimatePresence mode="popLayout">
            {filteredQuestions.map((q) => (
              <motion.div
                key={q.id}
                layout
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2 }}
              >
                <Card className="p-6 h-full flex flex-col justify-between hover:border-[#111111] hover:shadow-[0_8px_24px_rgba(0,0,0,0.04)] transition-all duration-300 group">
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-[#999999] uppercase tracking-wider">{q.category}</span>
                      <Badge variant={q.difficulty === "Hard" ? "warning" : q.difficulty === "Medium" ? "neutral" : "success"}>
                        {q.difficulty}
                      </Badge>
                    </div>
                    <h3 className="text-lg font-medium text-[#111111] leading-snug">
                      &quot;{q.title}&quot;
                    </h3>
                  </div>
                  
                  <div className="mt-8 flex items-center justify-between pt-4 border-t border-[#E5E5E5]">
                    <div className="text-sm text-[#666666] flex items-center gap-1.5">
                      <BookOpen size={14} />
                      Frequency: {q.frequency}
                    </div>
                    <Link href="/interview/setup">
                      <Button size="sm" variant="secondary" className="gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Play size={12} fill="currentColor" /> Practice
                      </Button>
                    </Link>
                  </div>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>
          {filteredQuestions.length === 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="col-span-full py-12 text-center text-[#666666]">
              No questions found matching your criteria.
            </motion.div>
          )}
        </motion.div>

      </div>
    </div>
  )
}
