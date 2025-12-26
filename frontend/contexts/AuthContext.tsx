"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { account } from "@/lib/appwrite";
import { Models, AppwriteException } from "appwrite";

interface AuthContextType {
    user: Models.User<Models.Preferences> | null;
    loading: boolean;
    login: (email: string, password: string) => Promise<void>;
    logout: () => Promise<void>;
    refreshSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<Models.User<Models.Preferences> | null>(null);
    const [loading, setLoading] = useState(true);

    // Check session on mount
    useEffect(() => {
        checkSession();
    }, []);

    const clearSession = async () => {
        // Try to delete the current session if it exists
        try {
            await account.deleteSession("current");
        } catch {
            // Session might already be invalid, that's fine
        }
        setUser(null);
    };

    const checkSession = async () => {
        try {
            const session = await account.get();
            setUser(session);
        } catch (error) {
            // Handle 401 specifically - session expired or invalid
            if (error instanceof AppwriteException && error.code === 401) {
                console.log("Session expired or invalid, clearing...");
                await clearSession();
            } else {
                // Other errors - still clear user state
                setUser(null);
            }
        } finally {
            setLoading(false);
        }
    };

    const refreshSession = async () => {
        setLoading(true);
        await checkSession();
    };

    const login = async (email: string, password: string) => {
        // Clear any existing invalid session first
        try {
            await account.deleteSession("current");
        } catch {
            // No existing session, that's fine
        }

        await account.createEmailPasswordSession(email, password);
        const session = await account.get();
        setUser(session);
    };

    const logout = async () => {
        await clearSession();
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, logout, refreshSession }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
}
