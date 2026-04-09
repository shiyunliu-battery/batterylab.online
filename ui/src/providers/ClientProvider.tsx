"use client";

import { createContext, useContext, useMemo, ReactNode } from "react";
import { Client } from "@langchain/langgraph-sdk";

interface ClientContextValue {
  client: Client;
}

const ClientContext = createContext<ClientContextValue | null>(null);

interface ClientProviderProps {
  children: ReactNode;
  deploymentUrl: string;
}

function resolveApiUrl(deploymentUrl: string): string {
  const normalized = deploymentUrl.trim();
  if (!normalized) {
    return deploymentUrl;
  }

  if (typeof window === "undefined") {
    return normalized;
  }

  try {
    return new URL(normalized, window.location.origin).toString();
  } catch {
    return normalized;
  }
}

export function ClientProvider({
  children,
  deploymentUrl,
}: ClientProviderProps) {
  const client = useMemo(() => {
    return new Client({
      apiUrl: resolveApiUrl(deploymentUrl),
      defaultHeaders: {
        "Content-Type": "application/json",
      },
    });
  }, [deploymentUrl]);

  const value = useMemo(() => ({ client }), [client]);

  return (
    <ClientContext.Provider value={value}>{children}</ClientContext.Provider>
  );
}

export function useClient(): Client {
  const context = useContext(ClientContext);

  if (!context) {
    throw new Error("useClient must be used within a ClientProvider");
  }
  return context.client;
}
