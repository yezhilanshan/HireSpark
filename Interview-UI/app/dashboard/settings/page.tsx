"use client"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { motion } from "motion/react"
import { User, FileText, Bell, Shield, UploadCloud } from "lucide-react"
import { useState } from "react"

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("profile")

  const tabs = [
    { id: "profile", label: "Profile", icon: User },
    { id: "resume", label: "Resume", icon: FileText },
    { id: "notifications", label: "Notifications", icon: Bell },
    { id: "security", label: "Security", icon: Shield },
  ]

  return (
    <div className="flex-1 overflow-y-auto p-8 lg:p-12">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-4xl mx-auto space-y-8"
      >
        <div>
          <h1 className="text-3xl font-serif text-[#111111] tracking-tight">Settings</h1>
          <p className="text-[#666666] mt-2">Manage your account preferences and configurations.</p>
        </div>

        <div className="flex flex-col md:flex-row gap-8">
          {/* Sidebar */}
          <div className="w-full md:w-64 shrink-0 space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab.id 
                    ? "bg-[#111111] text-white" 
                    : "text-[#666666] hover:bg-[#F5F5F5] hover:text-[#111111]"
                }`}
              >
                <tab.icon size={18} />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="flex-1">
            {activeTab === "profile" && (
              <Card className="p-6 border-[#E5E5E5] space-y-6">
                <div>
                  <h3 className="text-lg font-medium text-[#111111]">Personal Information</h3>
                  <p className="text-sm text-[#666666] mt-1">Update your personal details and public profile.</p>
                </div>
                <div className="space-y-4">
                  <div className="grid sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="firstName">First Name</Label>
                      <Input id="firstName" defaultValue="Alex" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="lastName">Last Name</Label>
                      <Input id="lastName" defaultValue="Chen" />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email">Email Address</Label>
                    <Input id="email" type="email" defaultValue="alex.chen@example.com" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="role">Target Role</Label>
                    <Input id="role" defaultValue="Senior Product Manager" />
                  </div>
                </div>
                <div className="pt-4 border-t border-[#E5E5E5] flex justify-end">
                  <Button className="bg-[#111111] text-white hover:bg-[#222222]">Save Changes</Button>
                </div>
              </Card>
            )}

            {activeTab === "resume" && (
              <Card className="p-6 border-[#E5E5E5] space-y-6">
                <div>
                  <h3 className="text-lg font-medium text-[#111111]">Resume Context</h3>
                  <p className="text-sm text-[#666666] mt-1">Upload your resume to personalize the AI interviewer&apos;s questions.</p>
                </div>
                
                <div className="border-2 border-dashed border-[#E5E5E5] rounded-xl p-8 flex flex-col items-center justify-center text-center hover:border-[#111111] hover:bg-[#FAFAFA] transition-colors cursor-pointer">
                  <div className="w-12 h-12 rounded-full bg-[#F5F5F5] flex items-center justify-center text-[#111111] mb-4">
                    <UploadCloud size={24} />
                  </div>
                  <h4 className="font-medium text-[#111111] mb-1">Click to upload or drag and drop</h4>
                  <p className="text-sm text-[#666666]">PDF, DOCX, or TXT (max. 5MB)</p>
                </div>

                <div className="bg-[#F5F5F5] rounded-lg p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <FileText size={20} className="text-[#666666]" />
                    <div>
                      <div className="text-sm font-medium text-[#111111]">alex_chen_resume_2026.pdf</div>
                      <div className="text-xs text-[#666666]">Uploaded on Oct 10, 2026</div>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" className="text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700">Remove</Button>
                </div>
              </Card>
            )}

            {(activeTab === "notifications" || activeTab === "security") && (
              <Card className="p-6 border-[#E5E5E5] flex items-center justify-center h-64 text-[#666666]">
                This section is under construction.
              </Card>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  )
}
