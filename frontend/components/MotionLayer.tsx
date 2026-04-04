'use client'

import { motion } from 'motion/react'

const ORBS = [
    {
        id: 'a',
        className: 'left-[-14rem] top-[-10rem] h-[26rem] w-[26rem] bg-[#E6DFC9]/55',
        x: 24,
        y: 36,
        duration: 14,
        delay: 0,
    },
    {
        id: 'b',
        className: 'right-[-12rem] top-[18%] h-[22rem] w-[22rem] bg-[#D9E6D8]/45',
        x: -28,
        y: 20,
        duration: 16,
        delay: 0.6,
    },
    {
        id: 'c',
        className: 'left-[38%] bottom-[-15rem] h-[24rem] w-[24rem] bg-[#DCD7EB]/35',
        x: 16,
        y: -24,
        duration: 18,
        delay: 1.2,
    },
]

export function MotionLayer() {
    return (
        <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_18%,rgba(255,255,255,0.72),transparent_46%),radial-gradient(circle_at_78%_22%,rgba(235,233,224,0.44),transparent_50%),radial-gradient(circle_at_52%_82%,rgba(212,209,193,0.3),transparent_55%)]" />

            {ORBS.map((orb) => (
                <motion.div
                    key={orb.id}
                    className={`absolute rounded-full blur-3xl ${orb.className}`}
                    animate={{
                        x: [0, orb.x, 0],
                        y: [0, orb.y, 0],
                        scale: [1, 1.06, 1],
                    }}
                    transition={{
                        duration: orb.duration,
                        repeat: Infinity,
                        repeatType: 'mirror',
                        ease: 'easeInOut',
                        delay: orb.delay,
                    }}
                />
            ))}

            <motion.div
                className="absolute inset-0 bg-[linear-gradient(120deg,transparent_10%,rgba(255,255,255,0.22)_40%,transparent_72%)]"
                animate={{ x: ['-14%', '14%', '-14%'], opacity: [0.14, 0.26, 0.14] }}
                transition={{ duration: 20, repeat: Infinity, ease: 'easeInOut' }}
            />
        </div>
    )
}
