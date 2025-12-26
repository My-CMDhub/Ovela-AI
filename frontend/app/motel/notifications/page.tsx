"use client";

import { useState, useEffect } from "react";
import { Phone, Clock, User, RefreshCw, Trash2, CheckCircle, XCircle, MessageSquare, Plus } from "lucide-react";

interface StaffNotification {
    $id: string;
    type: string;
    status: "pending" | "in_progress" | "completed" | "dismissed";
    customer_name: string;
    customer_phone: string;
    reason: string;
    urgency: "low" | "medium" | "high";
    staff_notes?: string;
    created_at?: string;
    completed_at?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://ovela-12c561a30285.herokuapp.com";

export default function NotificationsPage() {
    const [notifications, setNotifications] = useState<StaffNotification[]>([]);
    const [filter, setFilter] = useState<string>("pending");
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState<string | null>(null);

    // Notes modal
    const [showNotesModal, setShowNotesModal] = useState(false);
    const [notesText, setNotesText] = useState("");
    const [editingId, setEditingId] = useState<string | null>(null);

    // Create modal
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [createForm, setCreateForm] = useState({
        customer_name: "",
        customer_phone: "",
        reason: "",
        urgency: "medium",
        notification_type: "callback_request"
    });
    const [creating, setCreating] = useState(false);

    const fetchNotifications = async () => {
        setLoading(true);
        try {
            const url = filter
                ? `${API_URL}/api/notifications?status=${filter}`
                : `${API_URL}/api/notifications`;
            const res = await fetch(url);
            const data = await res.json();
            setNotifications(data.notifications || []);
        } catch (error) {
            console.error("Failed to fetch notifications:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchNotifications();
    }, [filter]);

    const createNotification = async () => {
        if (!createForm.customer_name || !createForm.customer_phone || !createForm.reason) {
            alert("Please fill all required fields");
            return;
        }
        setCreating(true);
        try {
            await fetch(`${API_URL}/api/notifications`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(createForm)
            });
            setShowCreateModal(false);
            setCreateForm({ customer_name: "", customer_phone: "", reason: "", urgency: "medium", notification_type: "callback_request" });
            fetchNotifications();
        } catch (error) {
            console.error("Failed to create:", error);
        } finally {
            setCreating(false);
        }
    };

    const updateStatus = async (id: string, status: string) => {
        setActionLoading(id);
        try {
            await fetch(`${API_URL}/api/notifications/${id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status })
            });
            fetchNotifications();
        } catch (error) {
            console.error("Failed to update:", error);
        } finally {
            setActionLoading(null);
        }
    };

    const deleteNotification = async (id: string) => {
        if (!confirm("Archive this notification? You can restore it later if needed.")) return;
        setActionLoading(id);
        try {
            await fetch(`${API_URL}/api/notifications/${id}`, { method: "DELETE" });
            fetchNotifications();
        } catch (error) {
            console.error("Failed to delete:", error);
        } finally {
            setActionLoading(null);
        }
    };

    const openNotesModal = (id: string, currentNotes: string) => {
        setEditingId(id);
        setNotesText(currentNotes || "");
        setShowNotesModal(true);
    };

    const saveNotes = async () => {
        if (!editingId) return;
        setActionLoading(editingId);
        try {
            await fetch(`${API_URL}/api/notifications/${editingId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ staff_notes: notesText })
            });
            setShowNotesModal(false);
            fetchNotifications();
        } catch (error) {
            console.error("Failed to save notes:", error);
        } finally {
            setActionLoading(null);
        }
    };

    const formatDate = (dateStr?: string) => {
        if (!dateStr) return "N/A";
        try {
            return new Date(dateStr).toLocaleDateString("en-AU", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
            });
        } catch {
            return dateStr;
        }
    };

    const getUrgencyBadge = (urgency: string) => {
        switch (urgency) {
            case "high":
                return <span className="px-2 py-1 bg-red-100 text-red-700 text-xs rounded-full">🔴 High</span>;
            case "medium":
                return <span className="px-2 py-1 bg-yellow-100 text-yellow-700 text-xs rounded-full">🟡 Medium</span>;
            default:
                return <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full">🟢 Low</span>;
        }
    };

    const getTypeBadge = (type: string) => {
        switch (type) {
            case "callback_request":
                return <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full">📞 Callback</span>;
            case "booking_approval":
                return <span className="px-2 py-1 bg-purple-100 text-purple-700 text-xs rounded-full">📋 Approval</span>;
            default:
                return <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-full">{type}</span>;
        }
    };

    return (
        <div className="p-4 md:p-8">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Staff Notifications</h1>
                    <p className="text-gray-500">Callback requests & human-in-loop operations</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => setShowCreateModal(true)}
                        className="flex items-center gap-2 px-4 py-2 bg-[#8B2332] text-white rounded-lg hover:bg-[#6B1A26]"
                    >
                        <Plus className="w-4 h-4" />
                        New Request
                    </button>
                    <button
                        onClick={fetchNotifications}
                        className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 dark:text-black"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </button>
                </div>
            </div>

            {/* Filter Tabs */}
            <div className="flex flex-wrap gap-2 mb-6">
                {["pending", "in_progress", "completed", "dismissed", ""].map((status) => (
                    <button
                        key={status || "all"}
                        onClick={() => setFilter(status)}
                        className={`px-4 py-2 rounded-lg font-medium transition-colors ${filter === status
                            ? "bg-[#8B2332] text-white"
                            : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                            }`}
                    >
                        {status === "" ? "All" : status.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}
                    </button>
                ))}
            </div>

            {/* Create Modal */}
            {showCreateModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-md shadow-xl">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                            New Callback Request
                        </h3>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Customer Name *</label>
                                <input
                                    type="text"
                                    value={createForm.customer_name}
                                    onChange={(e) => setCreateForm({ ...createForm, customer_name: e.target.value })}
                                    className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#8B2332]/20 outline-none dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                    placeholder="John Smith"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Phone Number *</label>
                                <input
                                    type="tel"
                                    value={createForm.customer_phone}
                                    onChange={(e) => setCreateForm({ ...createForm, customer_phone: e.target.value })}
                                    className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#8B2332]/20 outline-none dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                    placeholder="0412 345 678"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Reason *</label>
                                <input
                                    type="text"
                                    value={createForm.reason}
                                    onChange={(e) => setCreateForm({ ...createForm, reason: e.target.value })}
                                    className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#8B2332]/20 outline-none dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                    placeholder="Room availability inquiry"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Urgency</label>
                                <select
                                    value={createForm.urgency}
                                    onChange={(e) => setCreateForm({ ...createForm, urgency: e.target.value })}
                                    className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#8B2332]/20 outline-none dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                                >
                                    <option value="low">🟢 Low</option>
                                    <option value="medium">🟡 Medium</option>
                                    <option value="high">🔴 High</option>
                                </select>
                            </div>
                        </div>
                        <div className="flex gap-3 justify-end mt-6">
                            <button
                                onClick={() => setShowCreateModal(false)}
                                className="px-4 py-2 text-gray-600 hover:text-gray-800"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={createNotification}
                                disabled={creating}
                                className="flex items-center gap-2 px-4 py-2 bg-[#8B2332] text-white rounded-lg hover:bg-[#6B1A26] disabled:opacity-50"
                            >
                                {creating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                                Create
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Notifications List */}
            {loading ? (
                <div className="flex justify-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
                </div>
            ) : notifications.length === 0 ? (
                <div className="text-center py-12 bg-gray-50 dark:bg-gray-800 rounded-xl">
                    <Clock className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">No {filter.replace("_", " ")} notifications</p>
                </div>
            ) : (
                <div className="space-y-4">
                    {notifications.map((notif) => (
                        <div
                            key={notif.$id}
                            className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 md:p-6 hover:shadow-md transition-shadow"
                        >
                            <div className="flex flex-col lg:flex-row justify-between items-start gap-4">
                                <div className="space-y-2 flex-1">
                                    <div className="flex flex-wrap items-center gap-2">
                                        {getTypeBadge(notif.type)}
                                        {getUrgencyBadge(notif.urgency)}
                                    </div>

                                    <div className="flex items-center gap-3">
                                        <User className="w-5 h-5 text-gray-400" />
                                        <span className="font-medium text-gray-900 dark:text-white">
                                            {notif.customer_name}
                                        </span>
                                    </div>

                                    <div className="flex items-center gap-3 text-gray-500">
                                        <Phone className="w-4 h-4" />
                                        <a href={`tel:${notif.customer_phone}`} className="hover:text-indigo-600">
                                            {notif.customer_phone}
                                        </a>
                                    </div>

                                    <p className="text-gray-700 dark:text-gray-300">
                                        <span className="font-medium">Reason:</span> {notif.reason}
                                    </p>

                                    {notif.staff_notes && (
                                        <p className="text-sm text-gray-500 italic bg-gray-50 dark:bg-gray-700 p-2 rounded">
                                            📝 {notif.staff_notes}
                                        </p>
                                    )}

                                    <p className="text-xs text-gray-400">
                                        Received: {formatDate(notif.created_at)}
                                        {notif.completed_at && ` • Completed: ${formatDate(notif.completed_at)}`}
                                    </p>
                                </div>

                                {/* Actions */}
                                <div className="flex flex-wrap gap-2 w-full lg:w-auto">
                                    {notif.status === "pending" && (
                                        <>
                                            <button
                                                onClick={() => updateStatus(notif.$id, "in_progress")}
                                                disabled={actionLoading === notif.$id}
                                                className="flex items-center gap-2 px-3 py-2 bg-yellow-100 text-yellow-700 rounded-lg hover:bg-yellow-200 disabled:opacity-50"
                                            >
                                                <Clock className="w-4 h-4" />
                                                In Progress
                                            </button>
                                            <button
                                                onClick={() => updateStatus(notif.$id, "completed")}
                                                disabled={actionLoading === notif.$id}
                                                className="flex items-center gap-2 px-3 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 disabled:opacity-50"
                                            >
                                                <CheckCircle className="w-4 h-4" />
                                                Complete
                                            </button>
                                        </>
                                    )}

                                    {notif.status === "in_progress" && (
                                        <button
                                            onClick={() => updateStatus(notif.$id, "completed")}
                                            disabled={actionLoading === notif.$id}
                                            className="flex items-center gap-2 px-3 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                                        >
                                            <CheckCircle className="w-4 h-4" />
                                            Mark Complete
                                        </button>
                                    )}

                                    {notif.status !== "dismissed" && (
                                        <button
                                            onClick={() => updateStatus(notif.$id, "dismissed")}
                                            disabled={actionLoading === notif.$id}
                                            className="flex items-center gap-2 px-3 py-2 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 disabled:opacity-50"
                                        >
                                            <XCircle className="w-4 h-4" />
                                            Dismiss
                                        </button>
                                    )}

                                    <button
                                        onClick={() => openNotesModal(notif.$id, notif.staff_notes || "")}
                                        className="flex items-center gap-2 px-3 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200"
                                    >
                                        <MessageSquare className="w-4 h-4" />
                                        Notes
                                    </button>

                                    <button
                                        onClick={() => deleteNotification(notif.$id)}
                                        disabled={actionLoading === notif.$id}
                                        title="Archive this notification"
                                        className="flex items-center gap-2 px-3 py-2 bg-gray-200 text-gray-600 rounded-lg hover:bg-gray-300 disabled:opacity-50"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Notes Modal */}
            {showNotesModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-md shadow-xl">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                            Staff Notes
                        </h3>
                        <textarea
                            value={notesText}
                            onChange={(e) => setNotesText(e.target.value)}
                            placeholder="Add notes about this callback (e.g., 'Called back, left voicemail')"
                            rows={4}
                            className="w-full px-4 py-3 border border-gray-200 dark:border-gray-600 rounded-lg focus:border-blue-400 focus:ring-2 focus:ring-blue-100 outline-none transition resize-none mb-4 dark:bg-gray-700 dark:text-white"
                        />
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => setShowNotesModal(false)}
                                className="px-4 py-2 text-gray-600 hover:text-gray-800 transition"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={saveNotes}
                                disabled={actionLoading === editingId}
                                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                            >
                                {actionLoading === editingId ? (
                                    <RefreshCw className="w-4 h-4 animate-spin" />
                                ) : (
                                    <CheckCircle className="w-4 h-4" />
                                )}
                                Save Notes
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
