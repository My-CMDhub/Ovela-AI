"use client"

import { ColumnDef } from "@tanstack/react-table"
import { MoreHorizontal, ArrowUpDown, Clock, Phone, AlertCircle, CheckCircle, XCircle, MessageSquare, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"

export interface StaffNotification {
    $id: string;
    type: string;
    status: "pending" | "in_progress" | "completed" | "dismissed";
    customer_name: string;
    customer_phone: string;
    reason: string;
    urgency: "low" | "medium" | "high";
    staff_notes?: string;
    extra_data?: string;
    created_at?: string;
    completed_at?: string;
}

interface ColumnActions {
    onStatusUpdate: (id: string, status: StaffNotification["status"]) => void;
    onAddNotes: (id: string, currentNotes: string) => void;
    onDelete: (id: string) => void;
}

const formatDate = (dateStr?: string) => {
    if (!dateStr) return ""
    return new Date(dateStr).toLocaleString("en-AU", {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "numeric",
        hour12: true
    })
}

const getStatusBadgeVariant = (status: string) => {
    switch (status) {
        case "completed":
            return "bg-emerald-100 text-emerald-800 border-emerald-200"
        case "in_progress":
            return "bg-blue-100 text-blue-800 border-blue-200"
        case "dismissed":
            return "bg-slate-100 text-slate-800 border-slate-200"
        case "pending":
        default:
            return "bg-amber-100 text-amber-800 border-amber-200"
    }
}

const getUrgencyIcon = (urgency: string) => {
    switch (urgency) {
        case "high": return <AlertCircle className="w-4 h-4 text-red-500" />
        case "medium": return <AlertCircle className="w-4 h-4 text-amber-500" />
        default: return <Clock className="w-4 h-4 text-slate-400" />
    }
}

export const getColumns = ({ onStatusUpdate, onAddNotes, onDelete }: ColumnActions): ColumnDef<StaffNotification>[] => [
    {
        accessorKey: "urgency",
        header: "Urgency",
        cell: ({ row }) => {
            const urgency = (row.getValue("urgency") as string) || "low"
            return (
                <div className="flex items-center gap-2" title={`${urgency.toUpperCase()} Urgency`}>
                    {getUrgencyIcon(urgency)}
                    <span className={`text-xs font-medium uppercase ${urgency === 'high' ? 'text-red-600' : 'text-slate-500'}`}>
                        {urgency}
                    </span>
                </div>
            )
        },
    },
    {
        accessorKey: "customer_name",
        header: "Customer",
        cell: ({ row }) => {
            return (
                <div className="flex flex-col">
                    <span className="font-semibold text-slate-900">{row.getValue("customer_name")}</span>
                    <div className="flex items-center gap-1.5 text-xs text-slate-500 mt-0.5">
                        <Phone className="w-3 h-3" />
                        {row.original.customer_phone}
                    </div>
                </div>
            )
        },
    },
    {
        accessorKey: "type",
        header: "Type & Reason",
        cell: ({ row }) => {
            const type = row.getValue("type") as string
            const reason = row.original.reason
            return (
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600">
                        <MessageSquare className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col">
                        <span className="text-sm font-medium text-slate-700 capitalize">{type.replace(/_/g, " ")}</span>
                        <span className="text-xs text-slate-500 line-clamp-1 max-w-[200px]">{reason}</span>
                    </div>
                </div>
            )
        }
    },
    {
        accessorKey: "created_at",
        header: ({ column }) => {
            return (
                <Button
                    variant="ghost"
                    onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
                    className="-ml-4 hover:bg-transparent text-slate-600"
                >
                    Received
                    <ArrowUpDown className="ml-2 h-4 w-4" />
                </Button>
            )
        },
        cell: ({ row }) => {
            return (
                <div className="text-sm text-slate-600">
                    {formatDate(row.getValue("created_at"))}
                </div>
            )
        },
    },
    {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => {
            const status = row.getValue("status") as string
            return (
                <Badge variant="outline" className={`border-0 font-medium ${getStatusBadgeVariant(status)}`}>
                    {status.replace("_", " ")}
                </Badge>
            )
        },
    },
    {
        id: "actions",
        cell: ({ row }) => {
            const notification = row.original
            const status = notification.status

            return (
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" className="h-8 w-8 p-0 text-slate-500 hover:text-slate-900">
                            <span className="sr-only">Open menu</span>
                            <MoreHorizontal className="h-4 w-4" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                        <DropdownMenuLabel>Actions</DropdownMenuLabel>

                        {/* Status Actions */}
                        {status === "pending" && (
                            <>
                                <DropdownMenuItem onClick={() => onStatusUpdate(notification.$id, "in_progress")}>
                                    <Clock className="w-4 h-4 mr-2" /> Mark In Progress
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => onStatusUpdate(notification.$id, "completed")}>
                                    <CheckCircle className="w-4 h-4 mr-2" /> Mark Complete
                                </DropdownMenuItem>
                            </>
                        )}
                        {status === "in_progress" && (
                            <DropdownMenuItem onClick={() => onStatusUpdate(notification.$id, "completed")}>
                                <CheckCircle className="w-4 h-4 mr-2" /> Mark Complete
                            </DropdownMenuItem>
                        )}
                        {(status !== "dismissed" && status !== "completed") && (
                            <DropdownMenuItem onClick={() => onStatusUpdate(notification.$id, "dismissed")}>
                                <XCircle className="w-4 h-4 mr-2" /> Dismiss
                            </DropdownMenuItem>
                        )}

                        <DropdownMenuSeparator />

                        {/* Other Actions */}
                        <DropdownMenuItem onClick={() => onAddNotes(notification.$id, notification.staff_notes || "")}>
                            <MessageSquare className="w-4 h-4 mr-2" /> {notification.staff_notes ? "Edit Notes" : "Add Notes"}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => navigator.clipboard.writeText(notification.customer_phone)}>
                            <Phone className="w-4 h-4 mr-2" /> Copy Phone
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => window.location.href = `tel:${notification.customer_phone}`}>
                            <Phone className="w-4 h-4 mr-2" /> Call Customer
                        </DropdownMenuItem>

                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => onDelete(notification.$id)} className="text-red-600">
                            <Trash2 className="w-4 h-4 mr-2" /> Archive
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            )
        },
    },
]
