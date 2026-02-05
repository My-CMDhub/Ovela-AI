"use client";

import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Phone, Volume2, Skull, Briefcase, Activity } from 'lucide-react';
import { decodeMuLaw } from '@/lib/mulaw';

interface CallStatus {
    state: 'idle' | 'calling' | 'connected' | 'ended';
    callSid?: string;
    logs: string[];
}

export default function ColdCallDashboard() {
    const [phone, setPhone] = useState('');
    const [business, setBusiness] = useState('');
    const [pms, setPms] = useState('Little Hotelier');
    const [status, setStatus] = useState<CallStatus>({ state: 'idle', logs: [] });
    const [mode, setMode] = useState<'sales' | 'prank'>('sales'); // Prank Master Toggle
    const [prankType, setPrankType] = useState<'theft' | 'promotion'>('theft'); // Prank Type

    const wsRef = useRef<WebSocket | null>(null);
    const audioCtxRef = useRef<AudioContext | null>(null);

    // SEPARATE SCHEDULING QUEUES
    // This prevents the AI voice from getting stuck behind the User's audio stream
    const nextInboundTimeRef = useRef<number>(0);
    const nextOutboundTimeRef = useRef<number>(0);

    // Initialize Audio Context (user must interact first)
    const initAudio = () => {
        if (!audioCtxRef.current) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
            audioCtxRef.current = new AudioContext({
                sampleRate: 8000,
                latencyHint: 'interactive' // LOW LATENCY MODE
            });
        }
        if (audioCtxRef.current.state === 'suspended') {
            audioCtxRef.current.resume();
        }
    };

    const playAudio = (payload: string, direction: 'inbound' | 'outbound') => {
        if (!audioCtxRef.current) return;

        try {
            // Decode Base64
            const binaryString = window.atob(payload);
            const len = binaryString.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            const float32 = decodeMuLaw(bytes);
            const buffer = audioCtxRef.current.createBuffer(1, float32.length, 8000);
            buffer.copyToChannel(float32 as any, 0);

            // Select the correct queue based on direction
            // 'inbound' = User / Customer
            // 'outbound' = AI / Agent
            const timeRef = direction === 'inbound' ? nextInboundTimeRef : nextOutboundTimeRef;

            const currentTime = audioCtxRef.current.currentTime;

            // Drift Correction Logic (Per Queue)
            if (timeRef.current < currentTime) {
                timeRef.current = currentTime;
            }

            // Latency threshold - larger for outbound (AI) since packets are bigger/bufferred
            // Inbound = 200ms (small frequent packets)
            // Outbound = 500ms (larger buffered packets from AI)
            const maxLatency = direction === 'outbound' ? 0.5 : 0.2;

            if (timeRef.current > currentTime + maxLatency) {
                // Too far ahead - jump to near-current to catch up
                timeRef.current = currentTime + 0.02;
            }

            const source = audioCtxRef.current.createBufferSource();
            source.buffer = buffer;
            source.connect(audioCtxRef.current.destination);
            source.start(timeRef.current);

            timeRef.current += buffer.duration;

        } catch (e) {
            console.error("Audio playback error", e);
        }
    };

    const startCall = async () => {
        if (!phone || !business) {
            alert("Please enter phone and business name to start.");
            return;
        }

        initAudio();
        setStatus({ state: 'calling', logs: [`Initiating ${mode.toUpperCase()} call...`] });

        try {
            const params = new URLSearchParams({
                to: phone,
                business_name: business,
                pms: pms,
                mode: mode,
                prank_type: prankType
            });

            const res = await fetch(`http://localhost:8000/api/cold-calling/trigger?${params.toString()}`, {
                method: 'POST'
            });

            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();

            const sid = data.call_sid;
            setStatus(prev => ({ ...prev, state: 'connected', callSid: sid, logs: [...prev.logs, `Call SID: ${sid}`] }));

            connectObserver(sid);

        } catch (e) {
            console.error(e);
            setStatus(prev => ({ ...prev, state: 'idle', logs: [...prev.logs, `Error: ${String(e)}`] }));
        }
    };

    const connectObserver = (callSid: string) => {
        const wsUrl = `ws://localhost:8000/api/cold-calling/observe/${callSid}`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            setStatus(prev => ({ ...prev, logs: [...prev.logs, "Connected to Live Audio Stream 🟢"] }));
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.event === 'audio') {
                // Pass direction (inbound/outbound) to playAudio
                playAudio(data.media, data.direction || 'inbound');
            } else if (data.event === 'clear_audio' && data.direction === 'outbound') {
                // FLUSH OUTBOUND BUFFER (Barge-in)
                if (audioCtxRef.current) {
                    // Fast-forward the scheduler to "now", effectively dropping queued packets
                    nextOutboundTimeRef.current = audioCtxRef.current.currentTime;
                }
            }
        };

        ws.onclose = () => {
            setStatus(prev => ({ ...prev, state: 'ended', logs: [...prev.logs, "Stream Disconnected"] }));
        };

        wsRef.current = ws;
    };

    return (
        <div className="p-6 max-w-4xl mx-auto space-y-6">
            {/* Header & Mode Toggle */}
            <div className={`rounded-xl border shadow-sm overflow-hidden transition-colors duration-500 ${mode === 'prank' ? 'bg-red-950 border-red-900' : 'bg-white dark:bg-slate-950 border-slate-200 dark:border-slate-800'}`}>
                <div className={`p-6 border-b ${mode === 'prank' ? 'border-red-900 bg-red-900/20' : 'border-slate-200 dark:border-slate-800'}`}>
                    <div className="flex justify-between items-center">
                        <h2 className={`flex items-center gap-2 text-2xl font-semibold tracking-tight ${mode === 'prank' ? 'text-red-500' : ''}`}>
                            {mode === 'prank' ? <Skull className="w-6 h-6" /> : <Phone className="w-5 h-5 text-blue-500" />}
                            {mode === 'prank'
                                ? (prankType === 'theft' ? 'PRANK: COLES THEFT' : 'PRANK: SPEEDING FINE')
                                : 'Cold Call Agent'
                            }
                        </h2>

                        <div className="flex bg-slate-100 dark:bg-slate-900 p-1 rounded-lg">
                            <button
                                onClick={() => setMode('sales')}
                                className={`px-3 py-1 rounded-md text-sm font-medium transition-all ${mode === 'sales' ? 'bg-white shadow text-slate-900' : 'text-slate-500 hover:text-slate-900'}`}
                            >
                                <div className="flex items-center gap-2"><Briefcase size={14} /> Sales</div>
                            </button>
                            <button
                                onClick={() => setMode('prank')}
                                className={`px-3 py-1 rounded-md text-sm font-medium transition-all ${mode === 'prank' ? 'bg-red-600 shadow text-white' : 'text-slate-500 hover:text-red-500'}`}
                            >
                                <div className="flex items-center gap-2"><Skull size={14} /> Prank</div>
                            </button>
                        </div>
                    </div>

                    {/* Prank Type Selector - Only show in prank mode */}
                    {mode === 'prank' && (
                        <div className="mt-4 flex items-center gap-3">
                            <span className="text-sm text-red-300 font-medium">Prank Type:</span>
                            <div className="flex bg-red-900/30 p-1 rounded-lg">
                                <button
                                    onClick={() => setPrankType('theft')}
                                    className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${prankType === 'theft' ? 'bg-red-600 shadow text-white' : 'text-red-300 hover:text-white'}`}
                                >
                                    🛒 Theft (Coles)
                                </button>
                                <button
                                    onClick={() => setPrankType('promotion')}
                                    className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${prankType === 'promotion' ? 'bg-red-600 shadow text-white' : 'text-red-300 hover:text-white'}`}
                                >
                                    🚔 Speeding Fine (M1)
                                </button>
                            </div>
                        </div>
                    )}
                </div>

                {/* Controls */}
                <div className="p-6 space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                {mode === 'prank' ? 'Target Name (Victim)' : 'Business Name'}
                            </label>
                            <Input
                                placeholder={mode === 'prank' ? "e.g. John Doe" : "e.g. Seaside Motel"}
                                value={business}
                                onChange={e => setBusiness(e.target.value)}
                                className={mode === 'prank' ? 'border-red-900 bg-red-950 text-red-100 placeholder:text-red-800' : ''}
                            />
                        </div>

                        {mode === 'sales' && (
                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">PMS System</label>
                                <Input
                                    placeholder="e.g. Little Hotelier"
                                    value={pms}
                                    onChange={e => setPms(e.target.value)}
                                />
                            </div>
                        )}

                        <div className={`space-y-2 ${mode === 'prank' ? 'col-span-1' : 'col-span-2'}`}>
                            <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Phone Number</label>
                            <Input
                                placeholder="+61..."
                                value={phone}
                                onChange={e => setPhone(e.target.value)}
                                className={mode === 'prank' ? 'border-red-900 bg-red-950 text-red-100 placeholder:text-red-800' : ''}
                            />
                        </div>
                    </div>

                    <Button
                        className={`w-full text-white ${mode === 'prank' ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'}`}
                        size="lg"
                        onClick={startCall}
                        disabled={status.state === 'calling' || status.state === 'connected'}
                    >
                        {status.state === 'calling' ? 'Calling...' : status.state === 'connected' ? 'Live Call In Progress' : (mode === 'prank' ? 'DEPLOY OFFICER STEVE 🚨' : 'Start Cold Call')}
                    </Button>

                    {status.state === 'connected' && (
                        <div className={`flex items-center justify-center gap-8 p-4 rounded-lg animate-pulse ${mode === 'prank' ? 'bg-red-900/20' : 'bg-green-50 dark:bg-green-900/20'}`}>
                            <div className="flex items-center gap-2">
                                <Activity className={`w-5 h-5 ${mode === 'prank' ? 'text-red-500' : 'text-green-600'}`} />
                                <span className={`font-medium ${mode === 'prank' ? 'text-red-400' : 'text-green-800'}`}>Live Audio</span>
                            </div>
                            <div className="flex gap-2 text-xs opacity-70">
                                <span className="font-mono">IN (User)</span>
                                <span className="font-mono">OUT (AI)</span>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Logs */}
            <div className="bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-200 dark:border-slate-800">
                    <h3 className="text-lg font-semibold">Call Logs</h3>
                </div>
                <div className="p-0">
                    <div className="h-64 overflow-y-auto bg-slate-900 text-slate-100 p-4 font-mono text-sm">
                        {status.logs.length === 0 && <span className="text-slate-500">Ready to call...</span>}
                        {status.logs.map((log, i) => (
                            <div key={i} className="mb-1 border-b border-slate-800 pb-1 last:border-0">
                                <span className="text-slate-400">[{new Date().toLocaleTimeString()}]</span> {log}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
