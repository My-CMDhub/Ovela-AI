"use client";

import { useEffect, useState } from "react";
import { databases, DATABASE_ID } from "@/lib/appwrite";
import { Query } from "appwrite";
import { MessageSquare, ChevronDown, ChevronUp } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface Message {
    role: string;
    content: string;
    timestamp: string;
}

interface Conversation {
    $id: string;
    whatsapp_id: string;
    status: string;
    last_message: string;
    history: string;
    $updatedAt: string;
}

export default function ConversationsPage() {
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [filter, setFilter] = useState<"active" | "all">("active");

    useEffect(() => {
        fetchConversations();
    }, [filter]);

    const fetchConversations = async () => {
        setLoading(true);
        try {
            const queries = [Query.orderDesc("$updatedAt"), Query.limit(50)];

            if (filter === "active") {
                queries.unshift(Query.equal("status", "active"));
            }

            const res = await databases.listDocuments(DATABASE_ID, "conversations", queries);
            setConversations(res.documents as unknown as Conversation[]);
        } catch (error) {
            console.error("Error fetching conversations:", error);
        } finally {
            setLoading(false);
        }
    };

    const parseHistory = (historyStr: string): Message[] => {
        try {
            return JSON.parse(historyStr || "[]");
        } catch {
            return [];
        }
    };

    const formatTime = (dateStr: string) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return `${diffDays}d ago`;
    };

    return (
        <div>
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Conversations</h1>
                    <p className="text-gray-500 mt-1">WhatsApp conversations handled by Ovela</p>
                </div>

                {/* Filter */}
                <div className="flex gap-2">
                    {(["active", "all"] as const).map((f) => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            className={`px-4 py-2 text-sm rounded-lg transition ${filter === f
                                ? "bg-rose-600 text-white"
                                : "bg-white text-gray-600 border border-gray-200 hover:border-rose-300"
                                }`}
                        >
                            {f.charAt(0).toUpperCase() + f.slice(1)}
                        </button>
                    ))}
                </div>
            </div>

            {/* Conversations List */}
            <div className="space-y-3">
                {loading ? (
                    <div className="bg-white rounded-xl border border-gray-100 p-8 text-center text-gray-400">
                        Loading conversations...
                    </div>
                ) : conversations.length === 0 ? (
                    <div className="bg-white rounded-xl border border-gray-100 p-8 text-center text-gray-400">
                        No {filter === "active" ? "active " : ""}conversations found
                    </div>
                ) : (
                    conversations.map((conv) => {
                        const isExpanded = expandedId === conv.$id;
                        const history = parseHistory(conv.history);

                        return (
                            <motion.div
                                key={conv.$id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="bg-white rounded-xl border border-gray-100 overflow-hidden"
                            >
                                {/* Header */}
                                <button
                                    onClick={() => setExpandedId(isExpanded ? null : conv.$id)}
                                    className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition"
                                >
                                    <div className="flex items-center gap-4">
                                        <div className="w-10 h-10 bg-rose-100 rounded-full flex items-center justify-center">
                                            <MessageSquare className="w-5 h-5 text-rose-600" />
                                        </div>
                                        <div className="text-left">
                                            <p className="text-sm font-medium text-gray-900">{conv.whatsapp_id}</p>
                                            <p className="text-xs text-gray-400 truncate max-w-md">
                                                {conv.last_message || "No messages"}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <span
                                            className={`text-xs px-2 py-1 rounded-full ${conv.status === "active"
                                                ? "bg-green-100 text-green-700"
                                                : "bg-gray-100 text-gray-600"
                                                }`}
                                        >
                                            {conv.status}
                                        </span>
                                        <span className="text-xs text-gray-400">{formatTime(conv.$updatedAt)}</span>
                                        {isExpanded ? (
                                            <ChevronUp className="w-5 h-5 text-gray-400" />
                                        ) : (
                                            <ChevronDown className="w-5 h-5 text-gray-400" />
                                        )}
                                    </div>
                                </button>

                                {/* Expanded Chat History */}
                                <AnimatePresence>
                                    {isExpanded && (
                                        <motion.div
                                            initial={{ height: 0, opacity: 0 }}
                                            animate={{ height: "auto", opacity: 1 }}
                                            exit={{ height: 0, opacity: 0 }}
                                            className="border-t border-gray-100 bg-gray-50"
                                        >
                                            <div className="p-6 max-h-96 overflow-y-auto space-y-3">
                                                {history.length === 0 ? (
                                                    <p className="text-gray-400 text-sm text-center">No messages in history</p>
                                                ) : (
                                                    history.map((msg, idx) => (
                                                        <div
                                                            key={idx}
                                                            className={`flex ${msg.role === "assistant" ? "justify-start" : "justify-end"}`}
                                                        >
                                                            <div
                                                                className={`max-w-[70%] px-4 py-2 rounded-xl text-sm ${msg.role === "assistant"
                                                                    ? "bg-white border border-gray-200 text-gray-700"
                                                                    : "bg-rose-600 text-white"
                                                                    }`}
                                                            >
                                                                {msg.content}
                                                            </div>
                                                        </div>
                                                    ))
                                                )}
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </motion.div>
                        );
                    })
                )}
            </div>
        </div>
    );
}
