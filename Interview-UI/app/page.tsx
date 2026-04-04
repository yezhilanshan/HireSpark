import { Button } from "@/components/ui/button"
import Link from "next/link"

export default function LoginPage() {
  return (
    <div className="min-h-screen flex bg-[#FAF9F6]">
      {/* Left Panel */}
      <div className="hidden lg:flex flex-1 flex-col justify-between p-12 border-r border-[#E5E5E5] bg-[#F5F4F0]">
        <div>
          <div className="text-xl font-serif italic font-medium text-[#111111]">Aura</div>
        </div>
        <div className="max-w-md">
          <h1 className="text-4xl font-serif text-[#111111] leading-[1.1] tracking-tight mb-6">
            Refine your narrative. <br/> Master your interview.
          </h1>
          <p className="text-[#666666] text-lg leading-relaxed">
            Aura provides a calm, intelligent environment to practice and perfect your professional communication.
          </p>
        </div>
        <div className="text-sm text-[#999999]">
          © 2026 Aura Intelligence
        </div>
      </div>

      {/* Right Panel */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm space-y-8">
          <div className="text-center lg:text-left">
            <h2 className="text-2xl font-medium text-[#111111] tracking-tight">Sign in to Aura</h2>
            <p className="text-[#666666] mt-2 text-sm">Continue to your workspace</p>
          </div>

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-[#111111]">Email</label>
              <input 
                type="email" 
                placeholder="name@example.com" 
                className="w-full h-10 px-3 rounded-lg border border-[#E5E5E5] bg-white text-sm focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] transition-all"
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-[#111111]">Password</label>
                <a href="#" className="text-xs text-[#666666] hover:text-[#111111]">Forgot?</a>
              </div>
              <input 
                type="password" 
                className="w-full h-10 px-3 rounded-lg border border-[#E5E5E5] bg-white text-sm focus:outline-none focus:border-[#111111] focus:ring-1 focus:ring-[#111111] transition-all"
              />
            </div>
            
            <Link href="/dashboard" className="block pt-2">
              <Button className="w-full">Sign In</Button>
            </Link>
          </div>

          <div className="text-center text-sm text-[#666666]">
            Don&apos;t have an account? <a href="#" className="text-[#111111] hover:underline">Request access</a>
          </div>
        </div>
      </div>
    </div>
  )
}
