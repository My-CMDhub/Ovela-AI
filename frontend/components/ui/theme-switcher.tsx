"use client";

import { useEffect, useState } from "react";
import { Palette, X, Sparkles } from "lucide-react";

const THEMES = [
    {
        id: "arctic",
        name: "Arctic White (Default)",
        description: "Clean, crisp light mode with subtle gray tones.",
        primary: "#0f172a", // Slate 900
        variables: {
            "--theme-bg": "#FBF8F5", // Off-white
            "--theme-surface": "#ffffff", // White
            "--theme-border": "#e2e8f0", // Slate 200
            "--theme-text": "#0f172a", // Slate 900
            "--theme-muted": "#64748b", // Slate 500
            "--theme-primary": "#0f172a", // Slate 900
            "--theme-primary-hover": "#334155", // Slate 700
        }
    },
    {
        id: "cloud",
        name: "Cloud Gray",
        description: "Ultra-minimalist soft gray with sharp contrast.",
        primary: "#171717", // Neutral 900
        variables: {
            "--theme-bg": "#f4f4f5", // Zinc 100
            "--theme-surface": "#fafafa", // Neutral 50
            "--theme-border": "#e5e5e5", // Neutral 200
            "--theme-text": "#171717", // Neutral 900
            "--theme-muted": "#737373", // Neutral 500
            "--theme-primary": "#171717", // Neutral 900
            "--theme-primary-hover": "#404040", // Neutral 700
        }
    },
    {
        id: "sand",
        name: "Minimalist Sand",
        description: "Warm, professional beige focusing on clarity.",
        primary: "#292524", // Stone 800
        variables: {
            "--theme-bg": "#fafaf9", // Stone 50
            "--theme-surface": "#ffffff", // White
            "--theme-border": "#e7e5e4", // Stone 200
            "--theme-text": "#1c1917", // Stone 900
            "--theme-muted": "#78716c", // Stone 500
            "--theme-primary": "#292524", // Stone 800
            "--theme-primary-hover": "#44403c", // Stone 700
        }
    },
    {
        id: "frost",
        name: "Cerulean Frost",
        description: "Crisp white background with sharp, professional icy blue.",
        primary: "#0369a1", // Sky 700
        variables: {
            "--theme-bg": "#f8fafc", // Slate 50
            "--theme-surface": "#ffffff", // White
            "--theme-border": "#e2e8f0", // Slate 200
            "--theme-text": "#0f172a", // Slate 900
            "--theme-muted": "#64748b", // Slate 500
            "--theme-primary": "#0369a1", // Sky 700
            "--theme-primary-hover": "#075985", // Sky 800
        }
    },
    {
        id: "midnight",
        name: "Midnight Slate",
        description: "Modern, trust-inspiring dark theme with indigo accents.",
        primary: "#6366f1", // Indigo 500
        variables: {
            "--theme-bg": "#0f172a", // Slate 900
            "--theme-surface": "#1e293b", // Slate 800
            "--theme-border": "#334155", // Slate 700
            "--theme-text": "#f8fafc", // Slate 50
            "--theme-muted": "#94a3b8", // Slate 400
            "--theme-primary": "#6366f1", // Indigo 500
            "--theme-primary-hover": "#4f46e5", // Indigo 600
        }
    }
];

export function ThemeStudio() {
    const [isOpen, setIsOpen] = useState(false);
    const [activeThemeId, setActiveThemeId] = useState("arctic");
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
        // Load preference from local storage
        const saved = localStorage.getItem("ovela-theme") || "arctic";
        applyTheme(saved);
        setActiveThemeId(saved);
    }, []);

    const applyTheme = (id: string) => {
        const theme = THEMES.find(t => t.id === id) || THEMES[0];

        // Apply CSS variables to :root
        const root = document.documentElement;
        Object.entries(theme.variables).forEach(([key, value]) => {
            root.style.setProperty(key, value);
        });

        localStorage.setItem("ovela-theme", id);
        setActiveThemeId(id);
    };

    if (!mounted) return null;

    return (
        <>
            <button
                onClick={() => setIsOpen(true)}
                className="fixed bottom-6 right-6 p-4 rounded-full shadow-lg hover:opacity-90 transition-all z-50 flex items-center justify-center group"
                style={{ backgroundColor: "var(--theme-primary)", color: "var(--theme-bg)" }}
                title="Ovela Theme Studio"
            >
                <Palette className="w-6 h-6 group-hover:scale-110 transition-transform duration-300" />
            </button>

            {isOpen && (
                <div className="fixed bottom-24 right-6 w-80 border rounded-2xl shadow-2xl z-50 overflow-hidden transform origin-bottom-right transition-all duration-300"
                    style={{
                        backgroundColor: "var(--theme-surface)",
                        borderColor: "var(--theme-border)",
                        color: "var(--theme-text)"
                    }}>
                    <div className="p-4 border-b flex items-center justify-between"
                        style={{ borderColor: "var(--theme-border)", backgroundColor: "var(--theme-bg)" }}>
                        <div className="flex items-center gap-2">
                            <Sparkles className="w-4 h-4" style={{ color: "var(--theme-primary)" }} />
                            <div>
                                <h3 className="font-semibold text-sm">Theme Studio</h3>
                                <p className="text-xs" style={{ color: "var(--theme-muted)" }}>Ovela Branding Preview</p>
                            </div>
                        </div>
                        <button onClick={() => setIsOpen(false)}
                            className="p-1 rounded-md hover:opacity-70 transition-opacity"
                            style={{ color: "var(--theme-muted)" }}>
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    <div className="p-3 space-y-2 max-h-96 overflow-y-auto">
                        {THEMES.map(theme => (
                            <button
                                key={theme.id}
                                onClick={() => applyTheme(theme.id)}
                                className={`w-full text-left p-4 rounded-xl transition-all border ${activeThemeId === theme.id
                                    ? 'ring-1'
                                    : 'border-transparent hover:opacity-80'
                                    }`}
                                style={{
                                    borderColor: activeThemeId === theme.id ? "var(--theme-primary)" : "transparent",
                                    backgroundColor: activeThemeId === theme.id ? "var(--theme-bg)" : "transparent",
                                    "--tw-ring-color": "var(--theme-primary)"
                                } as React.CSSProperties}
                            >
                                <div className="flex items-center justify-between mb-2">
                                    <span className="font-medium text-sm">{theme.name}</span>
                                    <div className="flex gap-1 border rounded-full p-1" style={{ borderColor: theme.variables["--theme-border"] }}>
                                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: theme.primary }} />
                                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: theme.variables["--theme-surface"] }} />
                                    </div>
                                </div>
                                <p className="text-xs leading-relaxed" style={{ color: "var(--theme-muted)" }}>
                                    {theme.description}
                                </p>
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </>
    );
}
