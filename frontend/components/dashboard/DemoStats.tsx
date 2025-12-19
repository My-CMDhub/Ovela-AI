"use client"

import { useEffect, useState } from "react"
import { Phone } from "lucide-react"

interface DemoUser {
    $id: string
    name: string
    business_name: string
    phone: string
    latest_activity: string
    last_status: string
    attempt_count: number
}

interface DemoStatsData {
    total_demos: number
    unique_users: number
    recent_leads: DemoUser[]
}

export function DemoStats() {
    const [stats, setStats] = useState<DemoStatsData | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetchStats = async () => {
            try {
                // Use Next.js proxy (adds API key server-side)
                const res = await fetch(`/api/dashboard/demo-stats`)
                if (res.ok) {
                    const data = await res.json()
                    setStats(data)
                }
            } catch (error) {
                console.error("Failed to fetch demo stats", error)
            } finally {
                setLoading(false)
            }
        }

        fetchStats()
    }, [])

    if (loading) {
        return <div className="h-48 animate-pulse bg-gray-100 dark:bg-white/5 rounded-xl" />
    }

    if (!stats) return null

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl p-6 shadow-sm">
                    <div className="flex flex-row items-center justify-between space-y-0 pb-2 mb-2">
                        <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Demos</h3>
                        <Phone className="h-4 w-4 text-gray-400" />
                    </div>
                    <div>
                        <div className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total_demos}</div>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            from {stats.unique_users} unique users
                        </p>
                    </div>
                </div>
            </div>

            <div className="bg-white dark:bg-white/5 border border-gray-200 dark:border-white/10 rounded-xl overflow-hidden shadow-sm">
                <div className="p-6 border-b border-gray-200 dark:border-white/10">
                    <h3 className="font-semibold text-gray-900 dark:text-white">Recent Active Users</h3>
                </div>
                <div className="p-6">
                    <div className="space-y-4">
                        {stats.recent_leads.map((user) => (
                            <div key={user.$id} className="flex items-center justify-between border-b border-gray-100 dark:border-white/5 pb-4 last:border-0 last:pb-0">
                                <div>
                                    <div className="flex items-center gap-2">
                                        <p className="text-sm font-medium leading-none text-gray-900 dark:text-white">{user.business_name}</p>
                                        {user.attempt_count > 1 && (
                                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300">
                                                {user.attempt_count} attempts
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-xs text-muted-foreground mt-1 text-gray-500">{user.name} • {user.phone}</p>
                                </div>
                                <div className="text-right">
                                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${user.last_status === 'called'
                                        ? 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400'
                                        : 'bg-gray-100 text-gray-700 dark:bg-gray-500/20 dark:text-gray-400'
                                        }`}>
                                        {user.last_status}
                                    </span>
                                    <p className="text-xs text-muted-foreground mt-1 text-gray-500">
                                        {new Date(user.latest_activity).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </p>
                                </div>
                            </div>
                        ))}
                        {stats.recent_leads.length === 0 && (
                            <p className="text-sm text-muted-foreground text-center py-4">No demos yet.</p>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
