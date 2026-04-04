"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Camera, Mic, Settings2, ArrowRight, CheckCircle2, AlertCircle, Play } from "lucide-react"
import Link from "next/link"
import { motion } from "motion/react"

export default function SetupPage() {
  const [cameraStatus, setCameraStatus] = useState<"checking" | "ok" | "error">("checking")
  const [micStatus, setMicStatus] = useState<"checking" | "ok" | "error">("checking")
  const [interviewType, setInterviewType] = useState("product-sense")
  const [persona, setPersona] = useState("supportive")

  useEffect(() => {
    // Simulate hardware checks
    const timer1 = setTimeout(() => setCameraStatus("ok"), 1500)
    const timer2 = setTimeout(() => setMicStatus("ok"), 2000)
    return () => {
      clearTimeout(timer1)
      clearTimeout(timer2)
    }
  }, [])

  const isReady = cameraStatus === "ok" && micStatus === "ok"

  return (
    <div className="min-h-screen bg-[#FAF9F6] flex flex-col items-center justify-center p-6 font-sans">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-4xl grid md:grid-cols-2 gap-8"
      >
        {/* Left Column: Hardware Check */}
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-serif text-[#111111] tracking-tight">Pre-Interview Setup</h1>
            <p className="text-[#666666] mt-2">Let&apos;s make sure your audio and video are working perfectly.</p>
          </div>

          <Card className="p-6 bg-[#111111] text-white overflow-hidden relative aspect-video flex items-center justify-center border-0">
            {cameraStatus === "checking" ? (
              <div className="flex flex-col items-center gap-3 text-white/50">
                <Camera size={32} className="animate-pulse" />
                <span className="text-sm">Accessing camera...</span>
              </div>
            ) : cameraStatus === "ok" ? (
              <div className="absolute inset-0 bg-[#222222] flex items-center justify-center">
                <div className="text-white/30 flex flex-col items-center gap-3">
                  <Camera size={48} strokeWidth={1} />
                  <span className="text-sm uppercase tracking-widest">Camera Preview</span>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 text-red-400">
                <AlertCircle size={32} />
                <span className="text-sm">Camera access denied</span>
              </div>
            )}
          </Card>

          <div className="space-y-3">
            <div className="flex items-center justify-between p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-full ${cameraStatus === "ok" ? "bg-green-100 text-green-600" : "bg-[#F5F5F5] text-[#666666]"}`}>
                  <Camera size={18} />
                </div>
                <div>
                  <div className="font-medium text-sm text-[#111111]">Camera</div>
                  <div className="text-xs text-[#666666]">FaceTime HD Camera</div>
                </div>
              </div>
              {cameraStatus === "checking" && <div className="w-4 h-4 border-2 border-[#111111] border-t-transparent rounded-full animate-spin" />}
              {cameraStatus === "ok" && <CheckCircle2 size={18} className="text-green-600" />}
            </div>

            <div className="flex items-center justify-between p-4 rounded-xl border border-[#E5E5E5] bg-white">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-full ${micStatus === "ok" ? "bg-green-100 text-green-600" : "bg-[#F5F5F5] text-[#666666]"}`}>
                  <Mic size={18} />
                </div>
                <div>
                  <div className="font-medium text-sm text-[#111111]">Microphone</div>
                  <div className="text-xs text-[#666666]">MacBook Pro Microphone</div>
                </div>
              </div>
              {micStatus === "checking" && <div className="w-4 h-4 border-2 border-[#111111] border-t-transparent rounded-full animate-spin" />}
              {micStatus === "ok" && <CheckCircle2 size={18} className="text-green-600" />}
            </div>
          </div>
        </div>

        {/* Right Column: Interview Settings */}
        <div className="space-y-6 flex flex-col">
          <Card className="p-6 bg-white border-[#E5E5E5] flex-1 flex flex-col">
            <div className="flex items-center gap-2 mb-6">
              <Settings2 size={18} className="text-[#111111]" />
              <h2 className="text-lg font-medium text-[#111111]">Session Configuration</h2>
            </div>

            <div className="space-y-6 flex-1">
              <div className="space-y-3">
                <label className="text-sm font-medium text-[#111111]">Interview Type</label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { id: "product-sense", label: "Product Sense" },
                    { id: "execution", label: "Execution" },
                    { id: "behavioral", label: "Behavioral" },
                    { id: "technical", label: "Technical" },
                  ].map((type) => (
                    <button
                      key={type.id}
                      onClick={() => setInterviewType(type.id)}
                      className={`p-3 rounded-lg border text-sm text-left transition-colors ${
                        interviewType === type.id 
                          ? "border-[#111111] bg-[#111111] text-white" 
                          : "border-[#E5E5E5] hover:border-[#111111] text-[#666666]"
                      }`}
                    >
                      {type.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-3">
                <label className="text-sm font-medium text-[#111111]">Interviewer Persona</label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { id: "supportive", label: "Supportive & Guiding" },
                    { id: "strict", label: "Strict & Analytical" },
                    { id: "curious", label: "Curious & Probing" },
                    { id: "adversarial", label: "Adversarial (Hard)" },
                  ].map((p) => (
                    <button
                      key={p.id}
                      onClick={() => setPersona(p.id)}
                      className={`p-3 rounded-lg border text-sm text-left transition-colors ${
                        persona === p.id 
                          ? "border-[#111111] bg-[#111111] text-white" 
                          : "border-[#E5E5E5] hover:border-[#111111] text-[#666666]"
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-6 mt-6 border-t border-[#E5E5E5]">
              <Link href="/interview" className={!isReady ? "pointer-events-none" : ""}>
                <Button 
                  size="lg" 
                  className="w-full gap-2 group" 
                  disabled={!isReady}
                >
                  <Play size={16} fill="currentColor" className="group-hover:scale-110 transition-transform" />
                  {isReady ? "Start Interview" : "Checking Hardware..."}
                </Button>
              </Link>
            </div>
          </Card>
        </div>
      </motion.div>
    </div>
  )
}
