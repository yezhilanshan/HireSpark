"use client"

import { useParams } from "next/navigation"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ArrowLeft, Play, Pause, RotateCcw, MessageSquare, Target, Zap, Award } from "lucide-react"
import Link from "next/link"
import { useState } from "react"
import { motion, AnimatePresence } from "motion/react"

const transcript = [
  { time: "00:00", role: "interviewer", text: "Welcome. Let's start with a product sense question. How would you design a vending machine for a blind person?" },
  { time: "00:15", role: "interviewee", text: "That's a great question. To start, I'd like to clarify the goal. Are we focusing on a specific location, like a train station, or a general-purpose vending machine?" },
  { time: "00:28", role: "interviewer", text: "Let's assume it's a general-purpose vending machine in a public space, like a park or a mall." },
  { time: "00:35", role: "interviewee", text: "Okay. I'll structure my approach by first identifying the user and their specific pain points, then brainstorming solutions, and finally prioritizing them." },
  { time: "00:48", role: "interviewer", text: "Sounds good. Go ahead." },
  { time: "00:50", role: "interviewee", text: "The primary user is a person with severe visual impairment or total blindness. Their main pain points with a traditional vending machine are: 1) Finding the machine, 2) Knowing what's inside, 3) Making a selection, and 4) Retrieving the item and change." },
]

export default function SessionReviewPage() {
  const params = useParams()
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)

  return (
    <div className="flex-1 overflow-y-auto p-8 lg:p-12">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard/history">
              <Button variant="outline" size="icon" className="rounded-full w-10 h-10 border-[#E5E5E5] text-[#666666] hover:text-[#111111]">
                <ArrowLeft size={18} />
              </Button>
            </Link>
            <div>
              <div className="flex items-center gap-3 mb-1">
                <Badge variant="neutral">Product Sense</Badge>
                <span className="text-sm text-[#666666]">Oct 12, 2026</span>
              </div>
              <h1 className="text-2xl font-serif text-[#111111]">Design a Vending Machine</h1>
            </div>
          </div>
          <div className="text-right">
            <div className="text-3xl font-serif text-[#111111]">78<span className="text-lg text-[#999999]">/100</span></div>
            <div className="text-xs text-[#999999] uppercase tracking-wider mt-1">Overall Score</div>
          </div>
        </div>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Left Column: Video & Feedback */}
          <div className="lg:col-span-2 space-y-8">
            {/* Video Player Mock */}
            <Card className="overflow-hidden border-[#E5E5E5] bg-black aspect-video relative flex items-center justify-center group">
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-6">
                <div className="flex items-center gap-4 text-white">
                  <button onClick={() => setIsPlaying(!isPlaying)} className="hover:scale-110 transition-transform">
                    {isPlaying ? <Pause size={24} fill="currentColor" /> : <Play size={24} fill="currentColor" />}
                  </button>
                  <div className="flex-1 h-1.5 bg-white/30 rounded-full overflow-hidden">
                    <div className="h-full bg-[#E27A5F] w-1/3" />
                  </div>
                  <span className="text-sm font-mono">00:50 / 25:00</span>
                </div>
              </div>
              <div className="text-white/30 flex flex-col items-center gap-3">
                <Play size={48} />
                <span className="text-sm uppercase tracking-widest">Session Recording</span>
              </div>
            </Card>

            {/* AI Feedback */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium text-[#111111] flex items-center gap-2">
                <Zap size={18} className="text-[#E27A5F]" />
                AI Performance Analysis
              </h3>
              <div className="grid sm:grid-cols-2 gap-4">
                <Card className="p-5 border-[#E5E5E5] bg-[#FDF5F3]">
                  <h4 className="font-medium text-[#111111] mb-2 flex items-center gap-2">
                    <Target size={16} className="text-[#E27A5F]" /> Strengths
                  </h4>
                  <ul className="text-sm text-[#666666] space-y-2 list-disc list-inside">
                    <li>Excellent structure and framework application.</li>
                    <li>Strong user empathy and pain point identification.</li>
                    <li>Clear communication and check-ins with the interviewer.</li>
                  </ul>
                </Card>
                <Card className="p-5 border-[#E5E5E5] bg-[#F5F5F5]">
                  <h4 className="font-medium text-[#111111] mb-2 flex items-center gap-2">
                    <Award size={16} className="text-[#111111]" /> Areas for Improvement
                  </h4>
                  <ul className="text-sm text-[#666666] space-y-2 list-disc list-inside">
                    <li>Could have brainstormed more &quot;moonshot&quot; ideas.</li>
                    <li>Metrics for success were a bit generic.</li>
                    <li>Spent slightly too much time on edge cases.</li>
                  </ul>
                </Card>
              </div>
            </div>
          </div>

          {/* Right Column: Transcript */}
          <Card className="border-[#E5E5E5] flex flex-col h-[600px] lg:h-auto">
            <div className="p-4 border-b border-[#E5E5E5] flex items-center gap-2 bg-[#FAFAFA]">
              <MessageSquare size={16} className="text-[#666666]" />
              <h3 className="font-medium text-[#111111]">Transcript</h3>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {transcript.map((msg, i) => (
                <div key={i} className="group cursor-pointer">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[11px] font-medium uppercase tracking-wider ${msg.role === 'interviewer' ? 'text-[#111111]' : 'text-[#E27A5F]'}`}>
                      {msg.role === 'interviewer' ? 'Interviewer' : 'You'}
                    </span>
                    <span className="text-[10px] text-[#999999] group-hover:text-[#111111] transition-colors">{msg.time}</span>
                  </div>
                  <p className="text-sm text-[#444444] leading-relaxed group-hover:bg-[#F5F5F5] p-2 -mx-2 rounded-md transition-colors">
                    {msg.text}
                  </p>
                </div>
              ))}
            </div>
          </Card>
        </div>

      </div>
    </div>
  )
}
