"use client"

import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Mic, Square, ArrowRight, X, Loader2, Camera, User } from "lucide-react"
import Link from "next/link"
import { motion, AnimatePresence } from "motion/react"

type Message = {
  id: string;
  role: "interviewer" | "interviewee";
  text: string;
  time: string;
}

const initialMessages: Message[] = [
  {
    id: "1",
    role: "interviewer",
    text: "Hello Alex, welcome to the simulation. Today we'll be focusing on product sense and behavioral questions. Are you ready to begin?",
    time: "14:00"
  },
  {
    id: "2",
    role: "interviewee",
    text: "Hi, yes I'm ready.",
    time: "14:01"
  },
  {
    id: "3",
    role: "interviewer",
    text: "Great. Let's start with a behavioral question. Tell me about a time you had to make a difficult product decision with incomplete data. How did you proceed?",
    time: "14:01"
  }
]

export default function InterviewPage() {
  const [isRecording, setIsRecording] = useState(false)
  const [transcript, setTranscript] = useState("")
  const [timeElapsed, setTimeElapsed] = useState(0)
  const [isProcessing, setIsProcessing] = useState(false)
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  
  const chatEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, transcript])
  
  // Timer effect
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (isRecording) {
      interval = setInterval(() => {
        setTimeElapsed(prev => prev + 1)
      }, 1000)
    }
    return () => clearInterval(interval)
  }, [isRecording])

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0')
    const s = (seconds % 60).toString().padStart(2, '0')
    return `${m}:${s}`
  }

  // Simulated transcription effect
  useEffect(() => {
    if (isRecording) {
      const text = "I think the most important aspect of designing a product for this demographic is understanding their daily constraints. For example, when we look at their typical workflow, there are significant gaps in how they manage time. If we introduce a feature that automates..."
      let i = 0;
      setTranscript("")
      const interval = setInterval(() => {
        setTranscript(text.slice(0, i))
        i++
        if (i > text.length) clearInterval(interval)
      }, 40)
      return () => clearInterval(interval)
    }
  }, [isRecording])

  const handleStop = () => {
    setIsRecording(false)
    setIsProcessing(true)
    
    // Add transcript to messages
    if (transcript) {
      const newMessage: Message = {
        id: Date.now().toString(),
        role: "interviewee",
        text: transcript,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
      setMessages(prev => [...prev, newMessage])
      setTranscript("")
    }

    setTimeout(() => {
      setIsProcessing(false)
      // Simulate interviewer response
      const responseMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "interviewer",
        text: "That's a great example. Can you elaborate on how you measured the success of that automated feature once it was launched?",
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
      setMessages(prev => [...prev, responseMessage])
    }, 1500)
  }

  return (
    <div className="h-screen bg-[#FAF9F6] flex flex-col font-sans selection:bg-[#111111] selection:text-white overflow-hidden">
      {/* Top Navigation */}
      <header className="h-16 px-6 flex items-center justify-between border-b border-[#E5E5E5] bg-white/50 backdrop-blur-md shrink-0 z-10">
        <div className="flex items-center gap-4">
          <Link href="/dashboard" className="text-[#666666] hover:text-[#111111] transition-colors p-2 -ml-2 rounded-full hover:bg-[#F5F5F5]">
            <X size={20} />
          </Link>
          <div className="h-4 w-px bg-[#E5E5E5]" />
          <span className="text-sm font-medium text-[#111111]">Product Manager Simulation</span>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2 text-sm text-[#666666]">
            <motion.span 
              animate={{ opacity: isRecording ? [1, 0.4, 1] : 1 }}
              transition={{ repeat: Infinity, duration: 2 }}
              className={`w-2 h-2 rounded-full ${isRecording ? 'bg-[#E27A5F]' : 'bg-[#2E6A45]'}`} 
            />
            {isRecording ? 'Recording' : 'Session Active'}
          </div>
          <div className="text-sm font-mono text-[#111111] w-12 text-right">
            {formatTime(timeElapsed)}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col lg:flex-row overflow-hidden p-4 gap-4">
        
        {/* Center Column: Camera & Transcription */}
        <div className="flex-1 flex flex-col gap-4 min-w-0">
          
          {/* Camera Feed */}
          <div className="flex-1 bg-[#111111] rounded-2xl relative overflow-hidden flex items-center justify-center shadow-sm border border-[#222222]">
            {/* Recording Indicator */}
            <AnimatePresence>
              {isRecording && (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  className="absolute top-6 right-6 bg-black/40 backdrop-blur-md px-3 py-1.5 rounded-full text-white text-xs font-medium flex items-center gap-2 z-20 border border-white/10"
                >
                  <div className="w-2 h-2 rounded-full bg-[#E27A5F] animate-pulse" />
                  REC
                </motion.div>
              )}
            </AnimatePresence>

            {/* Camera Placeholder */}
            <div className="text-white/30 flex flex-col items-center gap-4">
              <Camera size={48} strokeWidth={1} />
              <p className="text-sm font-medium tracking-widest uppercase">Camera Active</p>
            </div>

            {/* User Label */}
            <div className="absolute bottom-6 left-6 bg-black/40 backdrop-blur-md px-4 py-2 rounded-xl text-white text-sm font-medium flex items-center gap-3 border border-white/10">
              <div className="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center">
                <User size={14} className="text-white" />
              </div>
              Alex (You)
            </div>
            
            {/* AI Interviewer PIP (Picture-in-Picture) */}
            <div className="absolute bottom-6 right-6 w-48 h-32 bg-[#222222] rounded-xl border border-white/10 overflow-hidden shadow-2xl flex items-center justify-center">
               <div className="relative flex items-center justify-center w-12 h-12">
                  <motion.div 
                    className="absolute inset-0 rounded-full border border-white/20 bg-white/5"
                    animate={{ scale: !isRecording && !isProcessing ? [1, 1.1, 1] : 1 }}
                    transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
                  />
                  <div className="w-6 h-6 rounded-full bg-white/80 z-10" />
                </div>
                <div className="absolute bottom-2 left-3 text-[10px] font-medium text-white/70 uppercase tracking-wider">
                  Interviewer
                </div>
            </div>
          </div>

          {/* Bottom: Transcription & Controls */}
          <div className="h-48 bg-white rounded-2xl border border-[#E5E5E5] p-6 flex flex-col shadow-sm shrink-0 relative">
            
            {/* Transcript Area */}
            <div className="flex-1 overflow-y-auto mb-4 pr-4">
              <AnimatePresence mode="wait">
                {transcript ? (
                  <motion.p 
                    key="transcript"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-lg text-[#111111] leading-relaxed font-serif"
                  >
                    {transcript}
                    {isRecording && <span className="inline-block w-2 h-5 bg-[#111111] ml-1 animate-pulse align-middle" />}
                  </motion.p>
                ) : (
                  <motion.p 
                    key="placeholder"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="text-lg text-[#999999] leading-relaxed font-serif italic"
                  >
                    {isProcessing ? "Processing your response..." : "Your spoken response will appear here in real-time..."}
                  </motion.p>
                )}
              </AnimatePresence>
            </div>

            {/* Controls */}
            <div className="flex items-center justify-between shrink-0 pt-2 border-t border-[#F5F5F5]">
              <div className="flex items-center gap-4">
                 <AnimatePresence mode="wait">
                  {!isRecording ? (
                    <motion.div key="start" initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.8, opacity: 0 }}>
                      <Button 
                        size="lg" 
                        className="rounded-full w-12 h-12 p-0 bg-[#111111] hover:bg-[#222222] hover:scale-105 transition-all shadow-md"
                        onClick={() => setIsRecording(true)}
                        disabled={isProcessing}
                      >
                        {isProcessing ? <Loader2 className="animate-spin text-white" size={20} /> : <Mic size={20} className="text-white" />}
                      </Button>
                    </motion.div>
                  ) : (
                    <motion.div key="stop" initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.8, opacity: 0 }}>
                      <Button 
                        size="lg" 
                        variant="outline"
                        className="rounded-full w-12 h-12 p-0 border-[#E5E5E5] text-[#E27A5F] hover:bg-[#FDF5F3] hover:border-[#E27A5F] hover:scale-105 transition-all shadow-sm"
                        onClick={handleStop}
                      >
                        <Square size={16} fill="currentColor" />
                      </Button>
                    </motion.div>
                  )}
                </AnimatePresence>
                
                {/* Audio Visualizer */}
                <AnimatePresence>
                  {isRecording && (
                    <motion.div 
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      className="flex items-center gap-1 h-8 overflow-hidden"
                    >
                      {[...Array(5)].map((_, i) => (
                        <motion.div
                          key={i}
                          className="w-1 bg-[#111111] rounded-full"
                          animate={{ 
                            height: ["20%", "80%", "30%", "100%", "40%"][i % 5],
                          }}
                          transition={{
                            repeat: Infinity,
                            repeatType: "mirror",
                            duration: 0.4 + (i * 0.1),
                            ease: "easeInOut"
                          }}
                        />
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              <Link href="/dashboard/history/1">
                <Button 
                  variant="secondary" 
                  className="gap-2 rounded-full bg-[#F5F5F5] hover:bg-[#EBE9E0] text-[#111111] transition-colors group"
                >
                  End Interview
                  <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
                </Button>
              </Link>
            </div>
          </div>

        </div>

        {/* Right Column: Chat History */}
        <aside className="w-full lg:w-[380px] xl:w-[420px] bg-white rounded-2xl border border-[#E5E5E5] flex flex-col shadow-sm shrink-0 overflow-hidden">
          <div className="p-5 border-b border-[#E5E5E5] bg-[#FAFAFA] shrink-0">
            <h3 className="font-medium text-[#111111]">Interview Transcript</h3>
            <p className="text-xs text-[#666666] mt-1">Real-time conversation history</p>
          </div>
          
          <div className="flex-1 overflow-y-auto p-5 space-y-6 bg-white">
            <AnimatePresence initial={false}>
              {messages.map((msg) => (
                <motion.div 
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex flex-col ${msg.role === "interviewee" ? "items-end" : "items-start"}`}
                >
                  <div className="flex items-center gap-2 mb-1.5 px-1">
                    <span className="text-[11px] font-medium text-[#111111] uppercase tracking-wider">
                      {msg.role === "interviewer" ? "Interviewer" : "You"}
                    </span>
                    <span className="text-[10px] text-[#999999]">{msg.time}</span>
                  </div>
                  <div 
                    className={`p-4 rounded-2xl max-w-[90%] text-sm leading-relaxed ${
                      msg.role === "interviewee" 
                        ? "bg-[#111111] text-white rounded-tr-sm" 
                        : "bg-[#F5F5F5] text-[#111111] rounded-tl-sm"
                    }`}
                  >
                    {msg.text}
                  </div>
                </motion.div>
              ))}
              
              {/* Typing indicator for transcript */}
              {transcript && (
                 <motion.div 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col items-end"
                >
                  <div className="flex items-center gap-2 mb-1.5 px-1">
                    <span className="text-[11px] font-medium text-[#111111] uppercase tracking-wider">
                      You
                    </span>
                    <span className="text-[10px] text-[#999999]">Typing...</span>
                  </div>
                  <div className="p-4 rounded-2xl max-w-[90%] text-sm leading-relaxed bg-[#111111] text-white/70 rounded-tr-sm italic">
                    {transcript}
                    <span className="inline-block w-1.5 h-4 bg-white/70 ml-1 animate-pulse align-middle" />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            <div ref={chatEndRef} />
          </div>
        </aside>

      </main>
    </div>
  )
}
