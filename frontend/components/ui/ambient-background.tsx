"use client"

import { Threads } from "./threads"

export function AmbientBackground() {
    return (
        <div className="absolute inset-0 overflow-hidden z-0 pointer-events-none">
            {/* Subtle Threads Wave Effect */}
            <div
                style={{
                    width: '100%',
                    height: '600px',
                    position: 'relative',
                    pointerEvents: 'auto'
                }}
            >
                <Threads
                    color={[0.6, 0.6, 0.6]} // Balanced visibility for both white and black backgrounds
                    amplitude={1.3}
                    distance={0.1}
                    enableMouseInteraction={true}
                />
            </div>
        </div>
    )
}
