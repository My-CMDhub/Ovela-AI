"use client"

import * as React from "react"
import {
    ColumnDef,
    ColumnFiltersState,
    SortingState,
    VisibilityState,
    flexRender,
    getCoreRowModel,
    getFilteredRowModel,
    getPaginationRowModel,
    getSortedRowModel,
    useReactTable,
} from "@tanstack/react-table"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
    DropdownMenu,
    DropdownMenuCheckboxItem,
    DropdownMenuContent,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Search, SlidersHorizontal, Filter, Plus, Bell } from "lucide-react"

interface DataTableProps<TData, TValue> {
    columns: ColumnDef<TData, TValue>[]
    data: TData[]
    loading?: boolean
    onRowClick?: (row: TData) => void
    onCreate?: () => void
}

export function DataTable<TData, TValue>({
    columns,
    data,
    loading = false,
    onRowClick,
    onCreate,
}: DataTableProps<TData, TValue>) {
    const [sorting, setSorting] = React.useState<SortingState>([])
    const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([])
    const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({})

    const table = useReactTable({
        data,
        columns,
        getCoreRowModel: getCoreRowModel(),
        getPaginationRowModel: getPaginationRowModel(),
        onSortingChange: setSorting,
        getSortedRowModel: getSortedRowModel(),
        onColumnFiltersChange: setColumnFilters,
        getFilteredRowModel: getFilteredRowModel(),
        onColumnVisibilityChange: setColumnVisibility,
        state: {
            sorting,
            columnFilters,
            columnVisibility,
        },
    })

    const statusColumn = table.getColumn("status")

    return (
        <div className="space-y-4">
            {/* Table Toolbar */}
            <div className="flex flex-col md:flex-row gap-4 justify-between items-start md:items-center">
                <div className="flex flex-1 flex-col sm:flex-row gap-2 w-full">
                    {/* Search Input */}
                    <div className="relative w-full max-w-sm">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <Input
                            placeholder="Search by customer..."
                            value={(table.getColumn("customer_name")?.getFilterValue() as string) ?? ""}
                            onChange={(event) =>
                                table.getColumn("customer_name")?.setFilterValue(event.target.value)
                            }
                            className="pl-9 h-10 bg-white border-slate-200 focus-visible:ring-slate-900"
                        />
                    </div>

                    {/* Status Filter */}
                    {statusColumn && (
                        <div className="flex items-center gap-2">
                            <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                    <Button variant="outline" size="sm" className="h-10 border-dashed text-slate-600 border-slate-300">
                                        <Filter className="mr-2 h-4 w-4" />
                                        Status
                                    </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="start" className="w-[200px]">
                                    {["pending", "in_progress", "completed", "dismissed"].map((status) => (
                                        <DropdownMenuCheckboxItem
                                            key={status}
                                            checked={(statusColumn.getFilterValue() as string)?.includes(status)}
                                            onCheckedChange={(checked) => {
                                                if (checked) statusColumn.setFilterValue(status)
                                                else statusColumn.setFilterValue(undefined)
                                            }}
                                            className="capitalize"
                                        >
                                            {status.replace("_", " ")}
                                        </DropdownMenuCheckboxItem>
                                    ))}
                                    <DropdownMenuCheckboxItem
                                        checked={!statusColumn.getFilterValue()}
                                        onCheckedChange={() => statusColumn.setFilterValue(undefined)}
                                        className="border-t mt-1 font-medium text-slate-500"
                                    >
                                        Clear Filter
                                    </DropdownMenuCheckboxItem>
                                </DropdownMenuContent>
                            </DropdownMenu>
                        </div>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    {/* View Toggle */}
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button variant="outline" size="sm" className="h-10 hidden lg:flex text-slate-600">
                                <SlidersHorizontal className="mr-2 h-4 w-4" />
                                View
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            {table
                                .getAllColumns()
                                .filter((column) => column.getCanHide())
                                .map((column) => {
                                    return (
                                        <DropdownMenuCheckboxItem
                                            key={column.id}
                                            className="capitalize"
                                            checked={column.getIsVisible()}
                                            onCheckedChange={(value) =>
                                                column.toggleVisibility(!!value)
                                            }
                                        >
                                            {column.id.replace("_", " ")}
                                        </DropdownMenuCheckboxItem>
                                    )
                                })}
                        </DropdownMenuContent>
                    </DropdownMenu>

                    {/* Create Button */}
                    {onCreate && (
                        <Button
                            onClick={onCreate}
                            className="h-10 bg-slate-900 hover:bg-slate-800 text-white shadow-sm"
                        >
                            <Plus className="mr-2 h-4 w-4" />
                            New Notification
                        </Button>
                    )}
                </div>
            </div>

            {/* Table */}
            <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm">
                <Table>
                    <TableHeader className="bg-slate-50/50">
                        {table.getHeaderGroups().map((headerGroup) => (
                            <TableRow key={headerGroup.id} className="hover:bg-transparent border-slate-100">
                                {headerGroup.headers.map((header) => {
                                    return (
                                        <TableHead key={header.id} className="py-4 px-4 font-semibold text-slate-700">
                                            {header.isPlaceholder
                                                ? null
                                                : flexRender(
                                                    header.column.columnDef.header,
                                                    header.getContext()
                                                )}
                                        </TableHead>
                                    )
                                })}
                            </TableRow>
                        ))}
                    </TableHeader>
                    <TableBody>
                        {table.getRowModel().rows?.length ? (
                            table.getRowModel().rows.map((row) => (
                                <TableRow
                                    key={row.id}
                                    data-state={row.getIsSelected() && "selected"}
                                    onClick={() => onRowClick && onRowClick(row.original)}
                                    className={`cursor-pointer transition-colors hover:bg-slate-50 border-slate-100 ${loading ? 'opacity-50 pointer-events-none' : ''}`}
                                >
                                    {row.getVisibleCells().map((cell) => (
                                        <TableCell key={cell.id} className="py-4 px-4">
                                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                                        </TableCell>
                                    ))}
                                </TableRow>
                            ))
                        ) : (
                            <TableRow>
                                <TableCell colSpan={columns.length} className="h-32 text-center text-slate-500">
                                    <div className="flex flex-col items-center justify-center gap-2">
                                        <Bell className="w-8 h-8 text-slate-300" />
                                        <p>{loading ? "Syncing notifications..." : "No notifications found."}</p>
                                    </div>
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between space-x-2 py-2">
                <div className="text-sm text-slate-500">
                    {table.getFilteredRowModel().rows.length} notifications
                </div>
                <div className="space-x-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => table.previousPage()}
                        disabled={!table.getCanPreviousPage()}
                        className="h-8 w-24"
                    >
                        Previous
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => table.nextPage()}
                        disabled={!table.getCanNextPage()}
                        className="h-8 w-24"
                    >
                        Next
                    </Button>
                </div>
            </div>
        </div>
    )
}
