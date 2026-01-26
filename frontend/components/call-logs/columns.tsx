"use client"

import { ColumnDef } from "@tanstack/react-table"
import { MoreHorizontal, ArrowUpDown, Phone, Clock, FileText } from "lucide-react"
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

// Define the shape of our data
export type TranscriptMessage = {
    role: "ai" | "user"
    text: string
    timestamp: string
}

export type CallLog = {
    id: string
    phone: string
    created_at: string
    duration_seconds: number
    exchange_count: number
    outcome: string
    transcript: TranscriptMessage[]
    booking_reference?: string
}

export const columns: ColumnDef<CallLog>[] = [
    {
        accessorKey: "created_at",
        header: ({ column }) => {
            return (
                <Button
                    variant="ghost"
                    onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
                    className="-ml-4 hover:bg-transparent"
                >
                    Date/Time
                    <ArrowUpDown className="ml-2 h-4 w-4" />
                </Button>
            )
        },
        cell: ({ row }) => {
            const date = new Date(row.getValue("created_at"))
            return (
                <div className="flex flex-col">
                    <span className="font-medium text-gray-900">
                        {date.toLocaleDateString("en-AU", { month: "short", day: "numeric" })}
                    </span>
                    <span className="text-xs text-gray-500">
                        {date.toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                </div>
            )
        },
    },
    {
        accessorKey: "phone",
        header: "Phone",
        cell: ({ row }) => {
            const phone = row.getValue("phone") as string
            return (
                <div className="flex items-center gap-2 font-mono text-sm">
                    <Phone className="w-3 h-3 text-gray-400" />
                    <a href={`tel:${phone}`} className="hover:text-blue-600 transition-colors">
                        {phone}
                    </a>
                </div>
            )
        },
    },
    {
        accessorKey: "duration_seconds",
        header: "Duration",
        cell: ({ row }) => {
            const seconds = row.getValue("duration_seconds") as number
            const mins = Math.floor(seconds / 60)
            const secs = seconds % 60
            return (
                <div className="flex items-center gap-1.5 text-gray-600">
                    <Clock className="w-3 h-3 text-gray-400" />
                    <span>{mins}:{secs.toString().padStart(2, '0')}</span>
                </div>
            )
        },
    },
    {
        accessorKey: "outcome",
        header: "Outcome",
        cell: ({ row }) => {
            const outcome = row.getValue("outcome") as string
            let variant: "default" | "secondary" | "destructive" | "outline" = "outline"
            let label = outcome || "Unknown"

            if (outcome.includes("completed") || outcome === "booking_made") {
                variant = "default" // we'll style this custom usually, but default badge works for now
                label = "Completed"
            } else if (outcome.includes("timeout") || outcome === "silence") {
                variant = "secondary"
                label = "Timeout"
            } else if (outcome.includes("spam") || outcome.includes("abuse")) {
                variant = "destructive"
                label = "Issue"
            } else if (outcome === "transferred") {
                variant = "secondary"
                label = "Transferred"
            }

            // Custom styles via className since standard Badge variants are limited
            let className = ""
            if (label === "Completed") className = "bg-green-100 text-green-700 hover:bg-green-200 border-green-200"
            if (label === "Timeout") className = "bg-yellow-50 text-yellow-700 hover:bg-yellow-100 border-yellow-200"
            if (label === "Issue") className = "bg-red-50 text-red-700 hover:bg-red-100 border-red-200"
            if (label === "Transferred") className = "bg-blue-50 text-blue-700 hover:bg-blue-100 border-blue-200"

            return <Badge variant="outline" className={`font-medium border-0 ${className}`}>{label}</Badge>
        },
    },
    {
        accessorKey: "transcript",
        header: "Summary",
        cell: ({ row }) => {
            const msgs = row.original.transcript
            const lastMsg = msgs.length > 0 ? msgs[msgs.length - 1].text : "No transcript"
            return (
                <div className="max-w-[300px] truncate text-sm text-gray-500" title={lastMsg}>
                    {lastMsg}
                </div>
            )
        }
    },
    {
        id: "actions",
        cell: ({ row }) => {
            const log = row.original

            return (
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" className="h-8 w-8 p-0">
                            <span className="sr-only">Open menu</span>
                            <MoreHorizontal className="h-4 w-4" />
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                        <DropdownMenuLabel>Actions</DropdownMenuLabel>
                        <DropdownMenuItem
                            onClick={() => navigator.clipboard.writeText(log.phone)}
                        >
                            Copy Phone Number
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => window.location.href = `tel:${log.phone}`}>
                            Call Guest
                        </DropdownMenuItem>
                        {/* View Transcript triggered via row click in main table usually, but can add here */}
                    </DropdownMenuContent>
                </DropdownMenu>
            )
        },
    },
]
