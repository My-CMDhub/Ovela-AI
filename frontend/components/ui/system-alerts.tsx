"use client";

import { useState, useEffect, useRef } from 'react';
import { databases, DATABASE_ID } from '@/lib/appwrite';
import { Query } from 'appwrite';
import { Bell, AlertTriangle, AlertCircle, Info, X, CheckCircle, ExternalLink } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

type AlertSeverity = 'critical' | 'error' | 'warning' | 'info';

interface SystemAlert {
    $id: string;
    title: string;
    message: string;
    severity: AlertSeverity;
    created_at: string;
    metadata_json?: string;
    status: 'new' | 'acknowledged' | 'resolved';
}

export default function SystemAlerts() {
    const [alerts, setAlerts] = useState<SystemAlert[]>([]);
    const [unreadCount, setUnreadCount] = useState(0);
    const [isOpen, setIsOpen] = useState(false);
    const [loading, setLoading] = useState(true);
    const dropdownRef = useRef<HTMLDivElement>(null);

    // Close dropdown when clicking outside
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Fetch alerts
    const fetchAlerts = async () => {
        // Check if we already failed with 404
        if (unreadCount === -1) return;

        try {
            const queries = [
                Query.orderDesc("$createdAt"),
                Query.limit(10)
            ];
            const response = await databases.listDocuments(
                DATABASE_ID,
                "system_alerts",
                queries
            );

            const documents = response.documents as unknown as SystemAlert[];
            setAlerts(documents);
            setUnreadCount(documents.filter(a => a.status === 'new').length);
        } catch (error: any) {
            // Silence "Collection not found" error to prevent console spam
            if (error?.code === 404 || error?.message?.includes('not be found')) {
                // Mark as "do not poll"
                setUnreadCount(-1); // Sentinel value
                return;
            }
            console.error("Failed to fetch system alerts:", error);
        } finally {
            setLoading(false);
        }
    };

    // Poll for alerts every 30s
    useEffect(() => {
        let isMounted = true;
        let interval: NodeJS.Timeout;

        const runFetch = async () => {
            // If we already failed with 404, or if we have a sentinel unreadCount, stop polling.
            if (unreadCount === -1) {
                if (interval) clearInterval(interval);
                return;
            }
            // If we already failed with 404, don't try again
            if (!loading && alerts.length === 0 && unreadCount === -1) return;
            await fetchAlerts();
        };

        runFetch();
        interval = setInterval(runFetch, 30000);
        return () => {
            isMounted = false;
            clearInterval(interval);
        };
    }, []);

    const markAsRead = async (alertId: string) => {
        try {
            await databases.updateDocument(
                DATABASE_ID,
                "system_alerts",
                alertId,
                { status: 'acknowledged' }
            );
            // Optimistic update
            setAlerts(prev => prev.map(a =>
                a.$id === alertId ? { ...a, status: 'acknowledged' } : a
            ));
            setUnreadCount(prev => Math.max(0, prev - 1));
        } catch (error) {
            console.error("Failed to update alert:", error);
        }
    };

    const getSeverityIcon = (severity: string) => {
        switch (severity) {
            case 'critical':
            case 'error':
                return <AlertCircle className="w-5 h-5 text-red-500" />;
            case 'warning':
                return <AlertTriangle className="w-5 h-5 text-amber-500" />;
            default:
                return <Info className="w-5 h-5 text-blue-500" />;
        }
    };

    const getSeverityColor = (severity: string) => {
        switch (severity) {
            case 'critical':
            case 'error':
                return 'bg-red-50 border-red-100 text-red-900';
            case 'warning':
                return 'bg-amber-50 border-amber-100 text-amber-900';
            default:
                return 'bg-blue-50 border-blue-100 text-blue-900';
        }
    };

    const formatTime = (isoString: string) => {
        const date = new Date(isoString);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

    return (
        <div className="relative" ref={dropdownRef}>
            {/* Bell Icon Trigger */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="relative p-2 text-gray-500 hover:bg-gray-100 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-amber-500"
            >
                <Bell className="w-5 h-5" />
                {unreadCount > 0 && (
                    <span className="absolute top-1 right-1 w-2.5 h-2.5 bg-red-500 border-2 border-white rounded-full"></span>
                )}
            </button>

            {/* Dropdown Panel */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: 10, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        className="absolute right-0 mt-2 w-80 md:w-96 bg-white rounded-xl shadow-2xl border border-gray-100 z-50 overflow-hidden"
                    >
                        <div className="px-4 py-3 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
                            <h3 className="font-semibold text-gray-900 text-sm">System Health</h3>
                            <span className="text-xs text-gray-500">{loading ? 'Updating...' : 'Live'}</span>
                        </div>

                        <div className="max-h-[24rem] overflow-y-auto">
                            {alerts.length === 0 ? (
                                <div className="p-8 text-center text-gray-400">
                                    <CheckCircle className="w-8 h-8 mx-auto mb-2 opacity-50 text-green-500" />
                                    <p className="text-sm">All systems operational</p>
                                </div>
                            ) : (
                                <ul className="divide-y divide-gray-50">
                                    {alerts.map((alert) => (
                                        <li
                                            key={alert.$id}
                                            className={`p-4 hover:bg-gray-50 transition-colors ${alert.status === 'new' ? 'bg-amber-50/10' : ''}`}
                                        >
                                            <div className="flex gap-3 items-start">
                                                <div className="mt-0.5 flex-shrink-0">
                                                    {getSeverityIcon(alert.severity)}
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex justify-between items-start mb-0.5">
                                                        <h4 className={`text-sm font-medium ${alert.severity === 'error' ? 'text-red-700' : 'text-gray-900'}`}>
                                                            {alert.title}
                                                        </h4>
                                                        <span className="text-xs text-gray-400 whitespace-nowrap ml-2">
                                                            {formatTime(alert.created_at)}
                                                        </span>
                                                    </div>
                                                    <p className="text-xs text-gray-600 leading-relaxed mb-2">
                                                        {alert.message}
                                                    </p>

                                                    {/* Metadata Summary */}
                                                    {alert.metadata_json && alert.metadata_json !== "{}" && (
                                                        <div className="text-[10px] text-gray-400 font-mono bg-gray-100/50 p-1.5 rounded truncate mb-2">
                                                            {alert.metadata_json.slice(0, 100)}...
                                                        </div>
                                                    )}

                                                    {alert.status === 'new' && (
                                                        <button
                                                            onClick={() => markAsRead(alert.$id)}
                                                            className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
                                                        >
                                                            Acknowledge
                                                        </button>
                                                    )}
                                                </div>
                                            </div>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>

                        <div className="p-3 border-t border-gray-100 bg-gray-50/50 text-center">
                            <button className="text-xs text-gray-500 hover:text-gray-900 font-medium">
                                View Full Error Log
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
