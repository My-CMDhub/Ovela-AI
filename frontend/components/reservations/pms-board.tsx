"use client";

import { useEffect, useState } from "react";
import { fetchWithAuth } from "@/lib/api-client";
import { Reservation } from "@/app/dashboard/reservations/page";
import { useTenant } from "@/contexts/TenantContext";
import { Loader2, RefreshCw } from "lucide-react";

interface Room {
    $id: string;
    room_number: string;
    room_type: string;
    base_rate: number;
    max_guests: number;
    status: string;
}

export function PmsBoard({ reservations }: { reservations: Reservation[] }) {
    const [rooms, setRooms] = useState<Room[]>([]);
    const [loading, setLoading] = useState(true);
    const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());
    const { tenant } = useTenant();
    
    // Generate next 7 days
    const dates = Array.from({ length: 7 }).map((_, i) => {
        const d = new Date();
        d.setDate(d.getDate() + i);
        return d.toISOString().split("T")[0];
    });

    useEffect(() => {
        fetchRooms();
        
        // Real-time tracking: Auto-refresh every 15 seconds
        const interval = setInterval(() => {
            fetchRooms(false); // background refresh
        }, 15000);
        
        return () => clearInterval(interval);
    }, [tenant.id]);

    const fetchRooms = async (showLoadingState = true) => {
        if (showLoadingState) setLoading(true);
        try {
            const res = await fetchWithAuth(`/api/dashboard/rooms?tenant_id=${tenant.id}`);
            const data = await res.json();
            if (data.success) {
                setRooms(data.rooms);
                setLastRefreshed(new Date());
            }
        } catch (error) {
            console.error("Error fetching rooms:", error);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="p-12 text-center text-slate-500 flex flex-col items-center justify-center space-y-3 bg-white rounded-xl shadow-sm border border-slate-200 min-h-[300px]">
                <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
                <span className="font-medium tracking-tight">Syncing Live Inventory...</span>
            </div>
        );
    }

    // Helper: Find booking for a specific room and date
    const getBookingForRoomDate = (roomNumber: string, dateStr: string) => {
        return reservations.find(r => {
            if (r.status === "cancelled" || r.status === "rejected") return false;
            // A booking occupies the room if check_in <= date AND check_out > date
            return r.room_number === roomNumber && r.check_in_date <= dateStr && r.check_out_date > dateStr;
        });
    };

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
                <div className="flex items-center gap-3">
                    <h3 className="font-semibold text-slate-900 tracking-tight">Live PMS Board</h3>
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-green-50 text-green-700 text-xs font-medium rounded-full border border-green-100">
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                        </span>
                        Live Sync
                    </div>
                </div>
                <div className="text-xs text-slate-500 flex items-center gap-2">
                    <span>Updated {lastRefreshed.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}</span>
                    <button onClick={() => fetchRooms(true)} className="p-1 hover:bg-slate-200 rounded transition-colors text-slate-600">
                        <RefreshCw className="h-3.5 w-3.5" />
                    </button>
                </div>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm text-left border-collapse">
                    <thead className="bg-slate-50/80 border-b border-slate-200 text-slate-600">
                        <tr>
                            <th className="px-6 py-4 font-semibold border-r border-slate-200 min-w-[180px]">Room</th>
                            {dates.map(date => {
                                const dateObj = new Date(date);
                                const isToday = date === dates[0];
                                return (
                                    <th key={date} className={`px-4 py-3 font-semibold border-r border-slate-200 min-w-[140px] ${isToday ? "bg-blue-50/50 text-blue-700" : ""}`}>
                                        <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">{dateObj.toLocaleDateString("en-US", { weekday: "short" })}</div>
                                        <div className="text-base">{dateObj.toLocaleDateString("en-US", { month: "short", day: "numeric" })}</div>
                                    </th>
                                );
                            })}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {rooms.map(room => (
                            <tr key={room.room_number} className="group hover:bg-slate-50/50 transition-colors">
                                <td className="px-6 py-4 border-r border-slate-200 bg-white group-hover:bg-slate-50/50 transition-colors">
                                    <div className="font-semibold text-slate-900 text-base tracking-tight">Room {room.room_number}</div>
                                    <div className="text-xs font-medium text-slate-500 capitalize bg-slate-100 inline-block px-2 py-0.5 rounded-md mt-1 border border-slate-200">{room.room_type}</div>
                                </td>
                                {(() => {
                                    const cells = [];
                                    let skipUntilIdx = -1;
                                    
                                    for (let i = 0; i < dates.length; i++) {
                                        if (i < skipUntilIdx) continue;
                                        
                                        const date = dates[i];
                                        const booking = getBookingForRoomDate(room.room_number, date);
                                        const isToday = date === dates[0];
                                        
                                        if (booking) {
                                            let colSpan = 1;
                                            for (let j = i + 1; j < dates.length; j++) {
                                                const nextBooking = getBookingForRoomDate(room.room_number, dates[j]);
                                                if (nextBooking && nextBooking.$id === booking.$id) {
                                                    colSpan++;
                                                } else {
                                                    break;
                                                }
                                            }
                                            skipUntilIdx = i + colSpan;
                                            
                                            cells.push(
                                                <td key={`${room.room_number}-${date}`} colSpan={colSpan} className={`p-2 border-r border-slate-100 relative ${isToday && !booking ? "bg-blue-50/20" : ""}`}>
                                                    <div className={`p-3 rounded-lg border shadow-sm h-full flex flex-col justify-center transition-all ${
                                                        booking.status === "confirmed" ? "bg-gradient-to-b from-green-50 to-green-100/50 border-green-200 text-green-900" :
                                                        booking.status === "checked_in" ? "bg-gradient-to-b from-blue-50 to-blue-100/50 border-blue-200 text-blue-900" :
                                                        "bg-gradient-to-b from-yellow-50 to-yellow-100/50 border-yellow-200 text-yellow-900"
                                                    }`}>
                                                        <div className="font-bold truncate text-[13px] tracking-tight">{booking.guest_name}</div>
                                                        <div className="text-[10px] font-medium opacity-80 mt-1 uppercase tracking-wider flex items-center justify-between">
                                                            <span>{booking.status.replace("_", " ")}</span>
                                                        </div>
                                                    </div>
                                                </td>
                                            );
                                        } else {
                                            cells.push(
                                                <td key={`${room.room_number}-${date}`} className={`p-2 border-r border-slate-100 relative ${isToday ? "bg-blue-50/20" : ""}`}>
                                                    <div className="h-full w-full min-h-[64px] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                                        <span className="text-[11px] text-slate-400 font-semibold uppercase tracking-wider bg-slate-100 px-2 py-1 rounded-md">Available</span>
                                                    </div>
                                                </td>
                                            );
                                        }
                                    }
                                    return cells;
                                })()}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
