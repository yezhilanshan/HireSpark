"use client"

import { Card } from "@/components/ui/card"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from "recharts"
import { motion } from "motion/react"
import { Target, TrendingUp, Clock, Award } from "lucide-react"

const trendData = [
  { name: "Week 1", score: 65 },
  { name: "Week 2", score: 68 },
  { name: "Week 3", score: 74 },
  { name: "Week 4", score: 72 },
  { name: "Week 5", score: 81 },
  { name: "Week 6", score: 85 },
]

const skillsData = [
  { subject: 'Product Sense', A: 85, fullMark: 100 },
  { subject: 'Execution', A: 78, fullMark: 100 },
  { subject: 'Behavioral', A: 92, fullMark: 100 },
  { subject: 'Technical', A: 65, fullMark: 100 },
  { subject: 'Strategy', A: 70, fullMark: 100 },
  { subject: 'Communication', A: 88, fullMark: 100 },
]

export default function AnalyticsPage() {
  return (
    <div className="flex-1 overflow-y-auto p-8 lg:p-12">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-6xl mx-auto space-y-8"
      >
        <div>
          <h1 className="text-3xl font-serif text-[#111111] tracking-tight">Analytics Overview</h1>
          <p className="text-[#666666] mt-2">Track your interview performance and identify areas for improvement.</p>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Average Score", value: "78", unit: "/100", icon: Target, trend: "+5% this month" },
            { label: "Interviews Completed", value: "24", unit: "", icon: Award, trend: "4 this week" },
            { label: "Total Practice Time", value: "12.5", unit: "hrs", icon: Clock, trend: "+2.5 hrs this week" },
            { label: "Current Streak", value: "3", unit: "days", icon: TrendingUp, trend: "Personal best: 7" },
          ].map((stat, i) => (
            <Card key={i} className="p-6 border-[#E5E5E5] bg-white">
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-full bg-[#F5F5F5] flex items-center justify-center text-[#111111]">
                  <stat.icon size={18} />
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-3xl font-serif text-[#111111]">
                  {stat.value}<span className="text-sm text-[#999999] ml-1 font-sans">{stat.unit}</span>
                </div>
                <div className="text-sm font-medium text-[#111111]">{stat.label}</div>
                <div className="text-xs text-[#666666]">{stat.trend}</div>
              </div>
            </Card>
          ))}
        </div>

        {/* Charts */}
        <div className="grid lg:grid-cols-2 gap-8">
          <Card className="p-6 border-[#E5E5E5] bg-white">
            <h3 className="text-lg font-medium text-[#111111] mb-6">Performance Trend</h3>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F5F5F5" />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#999999' }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#999999' }} domain={[0, 100]} />
                  <Tooltip 
                    contentStyle={{ borderRadius: '8px', border: '1px solid #E5E5E5', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}
                    itemStyle={{ color: '#111111', fontWeight: 500 }}
                  />
                  <Line type="monotone" dataKey="score" stroke="#111111" strokeWidth={2} dot={{ r: 4, fill: '#111111', strokeWidth: 0 }} activeDot={{ r: 6, fill: '#111111', stroke: '#fff', strokeWidth: 2 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card className="p-6 border-[#E5E5E5] bg-white">
            <h3 className="text-lg font-medium text-[#111111] mb-6">Skill Distribution</h3>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="70%" data={skillsData}>
                  <PolarGrid stroke="#E5E5E5" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#666666', fontSize: 12 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                  <Radar name="Score" dataKey="A" stroke="#111111" fill="#111111" fillOpacity={0.1} />
                  <Tooltip 
                    contentStyle={{ borderRadius: '8px', border: '1px solid #E5E5E5', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}
                    itemStyle={{ color: '#111111', fontWeight: 500 }}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

      </motion.div>
    </div>
  )
}
