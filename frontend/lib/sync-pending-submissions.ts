/**
 * Utility script to sync pending waitlist submissions from localStorage to Appwrite
 * 
 * This script helps recover submissions that were saved locally when Appwrite was unavailable.
 * Run this in the browser console or create a background sync service.
 */

import { waitlistDatabases, WAITLIST_DATABASE_ID, WAITLIST_COLLECTION_ID } from '@/lib/appwrite';
import { ID } from 'appwrite';

interface PendingSubmission {
    name: string;
    email: string;
    studioName: string;
    phone: string;
    studioSize: string;
    timestamp: string;
    synced: boolean;
}

export async function syncPendingSubmissions(): Promise<{
    synced: number;
    failed: number;
    total: number;
}> {
    const STORAGE_KEY = 'ovela_pending_submissions';

    try {
        const pendingData = localStorage.getItem(STORAGE_KEY);
        if (!pendingData) {
            console.log('ℹ️ No pending submissions to sync');
            return { synced: 0, failed: 0, total: 0 };
        }

        const pending: PendingSubmission[] = JSON.parse(pendingData);
        const unsynced = pending.filter(item => !item.synced);

        if (unsynced.length === 0) {
            console.log('✅ All submissions already synced');
            return { synced: 0, failed: 0, total: pending.length };
        }

        console.log(`🔄 Syncing ${unsynced.length} pending submissions...`);

        if (!waitlistDatabases || !WAITLIST_DATABASE_ID || !WAITLIST_COLLECTION_ID) {
            console.error('❌ Waitlist database not configured');
            return { synced: 0, failed: unsynced.length, total: pending.length };
        }

        let syncedCount = 0;
        let failedCount = 0;
        const results: PendingSubmission[] = [];

        for (const submission of pending) {
            if (submission.synced) {
                // Keep already synced items
                results.push(submission);
                continue;
            }

            try {
                const randomClientId = Math.floor(Math.random() * 100000);

                await waitlistDatabases.createDocument(
                    WAITLIST_DATABASE_ID,
                    WAITLIST_COLLECTION_ID,
                    ID.unique(),
                    {
                        clientId: randomClientId,
                        Name: submission.name,
                        email: submission.email,
                        phoneNumber: submission.phone,
                        StudioSize: submission.studioSize,
                        StudioName: submission.studioName,
                    }
                );

                console.log(`✅ Synced: ${submission.email}`);
                results.push({ ...submission, synced: true });
                syncedCount++;

                // Small delay to avoid rate limiting
                await new Promise(resolve => setTimeout(resolve, 500));
            } catch (error: any) {
                console.error(`❌ Failed to sync ${submission.email}:`, error);

                // If duplicate, mark as synced anyway
                if (error?.code === 409) {
                    console.log(`⚠️ ${submission.email} already exists, marking as synced`);
                    results.push({ ...submission, synced: true });
                    syncedCount++;
                } else {
                    // Keep for next sync attempt
                    results.push(submission);
                    failedCount++;
                }
            }
        }

        // Update localStorage with sync status
        localStorage.setItem(STORAGE_KEY, JSON.stringify(results));

        // If all synced, clean up localStorage
        if (failedCount === 0) {
            localStorage.removeItem(STORAGE_KEY);
            console.log('🎉 All submissions synced! localStorage cleared.');
        }

        return {
            synced: syncedCount,
            failed: failedCount,
            total: pending.length
        };
    } catch (error) {
        console.error('❌ Error during sync:', error);
        return { synced: 0, failed: 0, total: 0 };
    }
}

/**
 * Get count of pending submissions
 */
export function getPendingSubmissionsCount(): number {
    try {
        const pendingData = localStorage.getItem('ovela_pending_submissions');
        if (!pendingData) return 0;

        const pending: PendingSubmission[] = JSON.parse(pendingData);
        return pending.filter(item => !item.synced).length;
    } catch {
        return 0;
    }
}

/**
 * Clear all pending submissions (use with caution!)
 */
export function clearPendingSubmissions(): void {
    localStorage.removeItem('ovela_pending_submissions');
    console.log('🗑️ Pending submissions cleared from localStorage');
}

// Auto-sync on page load (optional)
if (typeof window !== 'undefined') {
    window.addEventListener('load', async () => {
        const pendingCount = getPendingSubmissionsCount();
        if (pendingCount > 0) {
            console.log(`📋 Found ${pendingCount} pending submissions. Auto-syncing...`);
            const result = await syncPendingSubmissions();
            console.log(`📊 Sync complete: ${result.synced} synced, ${result.failed} failed`);
        }
    });
}

// Browser console utility (for development)
if (typeof window !== 'undefined') {
    (window as any).ovelaSync = {
        sync: syncPendingSubmissions,
        count: getPendingSubmissionsCount,
        clear: clearPendingSubmissions,
    };
    console.log('💡 Ovela sync utilities available: window.ovelaSync.sync(), .count(), .clear()');
}
