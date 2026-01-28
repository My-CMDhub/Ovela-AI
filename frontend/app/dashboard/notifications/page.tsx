"use client";

import { useState, useEffect, useCallback } from "react";
import { getColumns, StaffNotification } from "@/components/notifications/columns";
import { DataTable } from "@/components/notifications/data-table";
import { RefreshCw, Plus, CheckCircle, Smartphone } from "lucide-react";
import { Button } from "@/components/ui/button";

const API_URL = "";
// Force relative path to use Next.js Proxy for auth and routing.

export default function NotificationsPage() {
    const [notifications, setNotifications] = useState<StaffNotification[]>([]);
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

    const fetchNotifications = useCallback(async () => {
        // Fetch generic list, large enough to cover recent history
        // Implementing client-side filtering for smoother UX
        setLoading(true);
        try {
            // Route through dashboard proxy (mapped to /api/motel/notifications on backend)
            const res = await fetch(`${API_URL}/api/dashboard/notifications?limit=200`);
            const data = await res.json();
            if (data.notifications) {
                setNotifications(data.notifications);
            }
        } catch (error) {
            console.error("Failed to fetch notifications:", error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchNotifications();

        // Auto-refresh every 30 seconds
        const interval = setInterval(() => {
            // optimized to not set loading state on poll
            fetch(`${API_URL}/api/dashboard/notifications?limit=200`)
                .then(res => res.json())
                .then(data => {
                    if (data.notifications) setNotifications(data.notifications);
                })
                .catch(console.error);
        }, 30000);

        return () => clearInterval(interval);
    }, [fetchNotifications]);

    const updateStatus = async (id: string, newStatus: StaffNotification["status"]) => {
        setActionLoading(id);
        try {
            await fetch(`${API_URL}/api/notifications/${id}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: newStatus })
            });
            // Update local state immediately
            setNotifications(prev => prev.map(n => n.$id === id ? { ...n, status: newStatus } : n));
        } catch (error) {
            console.error("Failed to update status:", error);
            alert("Failed to update status");
        } finally {
            setActionLoading(null);
        }
    };

    const deleteNotification = async (id: string) => {
        if (!confirm("Are you sure you want to archive this notification?")) return;
        setActionLoading(id);
        try {
            await fetch(`${API_URL}/api/notifications/${id}`, {
                method: "DELETE"
            });
            setNotifications(prev => prev.filter(n => n.$id !== id));
        } catch (error) {
            console.error("Failed to delete:", error);
            alert("Failed to delete notification");
        } finally {
            setActionLoading(null);
        }
    };

    const openNotesModal = (id: string, currentNotes: string) => {
        setEditingId(id);
        setNotesText(currentNotes);
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
            setNotifications(prev => prev.map(n => n.$id === editingId ? { ...n, staff_notes: notesText } : n));
            setShowNotesModal(false);
            setEditingId(null);
        } catch (error) {
            console.error("Failed to save notes:", error);
            alert("Failed to save notes");
        } finally {
            setActionLoading(null);
        }
    };

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
            alert("Failed to create notification");
        } finally {
            setCreating(false);
        }
    };

    const columns = getColumns({
        onStatusUpdate: updateStatus,
        onAddNotes: openNotesModal,
        onDelete: deleteNotification,
    });

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Notifications</h1>
                    <p className="text-slate-600 mt-1">
                        Manage callbacks and staff alerts
                    </p>
                </div>
            </div>

            {/* Data Table */}
            <DataTable
                columns={columns}
                data={notifications}
                loading={loading}
                onCreate={() => setShowCreateModal(true)}
            />

            {/* Create Modal */}
            {showCreateModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-xl p-6 w-full max-w-lg shadow-xl">
                        <h3 className="text-lg font-semibold text-slate-900 mb-4">Create Notification</h3>
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Customer Name</label>
                                    <input
                                        type="text"
                                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900"
                                        value={createForm.customer_name}
                                        onChange={e => setCreateForm({ ...createForm, customer_name: e.target.value })}
                                        placeholder="John Doe"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Phone Number</label>
                                    <input
                                        type="text"
                                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900"
                                        value={createForm.customer_phone}
                                        onChange={e => setCreateForm({ ...createForm, customer_phone: e.target.value })}
                                        placeholder="0400 000 000"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Reason</label>
                                <textarea
                                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900"
                                    value={createForm.reason}
                                    onChange={e => setCreateForm({ ...createForm, reason: e.target.value })}
                                    rows={3}
                                    placeholder="Needs to change booking dates..."
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Urgency</label>
                                <div className="flex gap-2">
                                    {['low', 'medium', 'high'].map((u) => (
                                        <button
                                            key={u}
                                            onClick={() => setCreateForm({ ...createForm, urgency: u })}
                                            className={`flex-1 py-2 px-3 rounded-lg capitalize text-sm font-medium transition-colors ${createForm.urgency === u
                                                ? 'bg-slate-900 text-white'
                                                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                                }`}
                                        >
                                            {u}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>
                        <div className="flex gap-3 justify-end mt-6">
                            <button
                                onClick={() => setShowCreateModal(false)}
                                className="px-4 py-2 text-slate-600 hover:text-slate-800 font-medium"
                            >
                                Cancel
                            </button>
                            <Button
                                onClick={createNotification}
                                disabled={creating}
                                className="bg-slate-900 hover:bg-slate-800 text-white"
                            >
                                {creating ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
                                Create
                            </Button>
                        </div>
                    </div>
                </div>
            )}

            {/* Notes Modal */}
            {showNotesModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
                        <h3 className="text-lg font-semibold text-slate-900 mb-4">
                            Staff Notes
                        </h3>
                        <textarea
                            value={notesText}
                            onChange={(e) => setNotesText(e.target.value)}
                            placeholder="Add notes about this callback (e.g., 'Called back, left voicemail')"
                            rows={4}
                            className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 outline-none transition resize-none mb-4"
                        />
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={() => setShowNotesModal(false)}
                                className="px-4 py-2 text-slate-600 hover:text-slate-800 transition font-medium"
                            >
                                Cancel
                            </button>
                            <Button
                                onClick={saveNotes}
                                disabled={actionLoading === editingId}
                                className="bg-slate-900 hover:bg-slate-800 text-white"
                            >
                                {actionLoading === editingId ? (
                                    <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                                ) : (
                                    <CheckCircle className="w-4 h-4 mr-2" />
                                )}
                                Save Notes
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
