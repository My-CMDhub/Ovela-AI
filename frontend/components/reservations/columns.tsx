"use client"

import { ColumnDef } from "@tanstack/react-table"
import { MoreHorizontal, ArrowUpDown, Calendar, User, Phone, BedDouble, CheckCircle, XCircle, Clock, AlertCircle } from "lucide-react"
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

export type Reservation = {
    $id: string
    guest_name: string
    guest_phone: string
    guest_email: string
    room_type: string
    check_in_date: string
    check_out_date: string
    num_guests: number
    num_nights: number
    rate_per_night: number
    total_amount: number
    status: string
    source: string
    booking_reference: string
    payment_link_url?: string
    payment_status?: string
    notes: string
    created_at: string
}

const formatDate = (dateStr: string) => {
    if (!dateStr) return ""
    return new Date(dateStr).toLocaleDateString("en-AU", { month: "short", day: "numeric" })
}

const getStatusBadgeVariant = (status: string) => {
    switch (status) {
        case "confirmed":
        case "paid":
        case "checked_in":
            return "default" // Green-ish/Primary
        case "pending":
        case "link_sent":
        case "approved":
            return "secondary" // Yellow/Blue/Warning
        case "cancelled":
        case "rejected":
            return "destructive"
        default:
            return "outline"
    }
}

// Custom styles for specific statuses to match requested "Classic Professional" look
const getStatusStyles = (status: string) => {
    switch (status) {
        case "confirmed": return "bg-emerald-100 text-emerald-800 border-emerald-200" // Natural green
        case "paid": return "bg-emerald-100 text-emerald-800 border-emerald-200"
        case "checked_in": return "bg-blue-100 text-blue-800 border-blue-200"
        case "pending":
        case "pending_confirmation": return "bg-amber-100 text-amber-800 border-amber-200" // Gold/Amber
        case "link_sent": return "bg-sky-100 text-sky-800 border-sky-200"
        case "approved": return "bg-sky-100 text-sky-800 border-sky-200"
        case "cancelled": return "bg-slate-100 text-slate-800 border-slate-200" // Grey for cancelled
        case "rejected": return "bg-red-100 text-red-800 border-red-200"
        default: return "bg-slate-100 text-slate-800 border-slate-200"
    }
}

export const columns: ColumnDef<Reservation>[] = [
    {
        accessorKey: "guest_name",
        header: "Guest",
        cell: ({ row }) => {
            return (
                <div className="flex flex-col">
                    <span className="font-semibold text-slate-900">{row.getValue("guest_name")}</span>
                    <div className="flex items-center gap-1.5 text-xs text-slate-500 mt-0.5">
                        <Phone className="w-3 h-3" />
                        {row.original.guest_phone}
                    </div>
                </div>
            )
        },
    },
    {
        accessorKey: "room_type",
        header: "Room",
        cell: ({ row }) => {
            const type = row.getValue("room_type") as string
            const formatType = type.charAt(0).toUpperCase() + type.slice(1)
            return (
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600">
                        <BedDouble className="w-4 h-4" />
                    </div>
                    <div className="flex flex-col">
                        <span className="text-sm font-medium text-slate-700">{formatType}</span>
                        <span className="text-xs text-slate-500">{row.original.num_guests} Guests</span>
                    </div>
                </div>
            )
        }
    },
    {
        accessorKey: "check_in_date",
        header: ({ column }) => {
            return (
                <Button
                    variant="ghost"
                    onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
                    className="-ml-4 hover:bg-transparent text-slate-600"
                >
                    Dates
                    <ArrowUpDown className="ml-2 h-4 w-4" />
                </Button>
            )
        },
        cell: ({ row }) => {
            return (
                <div className="flex items-center gap-2 text-sm text-slate-700">
                    <Calendar className="w-4 h-4 text-slate-400" />
                    <span>
                        {formatDate(row.getValue("check_in_date"))}
                        <span className="text-slate-400 mx-1">→</span>
                        {formatDate(row.original.check_out_date)}
                    </span>
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
                <Badge variant="outline" className={`border-0 font-medium ${getStatusStyles(status)}`}>
                    {status.replace("_", " ")}
                </Badge>
            )
        },
    },
    {
        accessorKey: "booking_reference",
        header: "Reference",
        cell: ({ row }) => <span className="font-mono text-xs text-slate-500">{row.getValue("booking_reference")}</span>
    },
    {
        id: "actions",
        cell: ({ row }) => {
            const reservation = row.original
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
                        <DropdownMenuItem onClick={() => navigator.clipboard.writeText(reservation.booking_reference)}>
                            Copy Reference
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onSelect={() => window.location.href = `tel:${reservation.guest_phone}`}>
                            Call Guest
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            )
        },
    },
]
