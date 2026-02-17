"use client";

import { useEffect, useState } from "react";
import { AudioVisualizer3D } from "../../components/AudioVisualizer3D";

export default function VisualizerPage() {
    const [isRecording, setIsRecording] = useState(false);
    const [audioStream, setAudioStream] = useState<MediaStream | null>(null);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: false,
                    autoGainControl: true,
                },
            });
            setAudioStream(stream);
            setIsRecording(true);
        } catch (error) {
            console.error("Microphone access denied:", error);
            alert("Please allow microphone access.");
        }
    };

    const stopRecording = () => {
        if (audioStream) {
            audioStream.getTracks().forEach((track) => track.stop());
            setAudioStream(null);
        }
        setIsRecording(false);
    };

    useEffect(() => {
        return () => {
            if (audioStream) {
                audioStream.getTracks().forEach((track) => track.stop());
            }
        };
    }, [audioStream]);

    return (
        <main className="relative w-full h-screen bg-[#050510] overflow-hidden flex flex-col items-center justify-center">
            {/* 3D Visualizer */}
            <div className="absolute inset-0 z-10">
                <AudioVisualizer3D audioStream={audioStream} isActive={isRecording} />
            </div>

            {/* Control Button - Floating Action Button (FAB) Style */}
            <div className="absolute bottom-12 z-20">
                <button
                    onClick={isRecording ? stopRecording : startRecording}
                    className={`
            w-14 h-14 rounded-full flex items-center justify-center
            transition-all duration-300 ease-out backdrop-blur-md border border-white/10
            shadow-2xl hover:scale-105 active:scale-95
            ${isRecording
                            ? 'bg-red-500/20 text-red-500 hover:bg-red-500/30 ring-1 ring-red-500/50'
                            : 'bg-white/5 text-white/70 hover:bg-white/10 hover:text-white'
                        }
          `}
                >
                    {isRecording ? (
                        // Square Stop Icon
                        <div className="w-4 h-4 bg-current rounded-sm shadow-[0_0_10px_currentColor]" />
                    ) : (
                        // Microphone Icon
                        <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24" stroke="none">
                            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                        </svg>
                    )}
                </button>
            </div>
        </main>
    );
}
