import { Client, Account, Databases } from "appwrite";

// ===========================================
// DASHBOARD CLIENT (Ovela AI - customer data)
// ===========================================
const DASHBOARD_ENDPOINT = process.env.NEXT_PUBLIC_APPWRITE_ENDPOINT || "https://api.ovela.dev/v1";
const DASHBOARD_PROJECT_ID = process.env.NEXT_PUBLIC_APPWRITE_PROJECT_ID || "";

const client = new Client()
    .setEndpoint(DASHBOARD_ENDPOINT)
    .setProject(DASHBOARD_PROJECT_ID);

const account = new Account(client);
const databases = new Databases(client);

// Dashboard database ID
const DATABASE_ID = process.env.NEXT_PUBLIC_APPWRITE_DATABASE_ID || "6947b8300005f5863f96";


// ===========================================
// WAITLIST CLIENT (separate project)
// ===========================================
const WAITLIST_PROJECT_ID = process.env.NEXT_PUBLIC_WAITLIST_PROJECT_ID || "";
const WAITLIST_DATABASE_ID = process.env.NEXT_PUBLIC_WAITLIST_DATABASE_ID || "";
const WAITLIST_COLLECTION_ID = process.env.NEXT_PUBLIC_WAITLIST_COLLECTION_ID || "clients";

// Only create waitlist client if project ID is configured
let waitlistClient: Client | null = null;
let waitlistDatabases: Databases | null = null;

if (WAITLIST_PROJECT_ID) {
    waitlistClient = new Client()
        .setEndpoint(DASHBOARD_ENDPOINT) // Same Sydney endpoint
        .setProject(WAITLIST_PROJECT_ID);
    waitlistDatabases = new Databases(waitlistClient);
}

export {
    // Dashboard exports
    client,
    account,
    databases,
    DATABASE_ID,
    // Waitlist exports
    waitlistClient,
    waitlistDatabases,
    WAITLIST_DATABASE_ID,
    WAITLIST_COLLECTION_ID
};
