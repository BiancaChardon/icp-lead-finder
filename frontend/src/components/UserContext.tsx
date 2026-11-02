"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { User } from "@/lib/types";

interface UserContextValue {
  user: User;
  authRequired: boolean;
}

const UserContext = createContext<UserContextValue | null>(null);

export function UserProvider({ user, authRequired, children }: UserContextValue & { children: ReactNode }) {
  return <UserContext.Provider value={{ user, authRequired }}>{children}</UserContext.Provider>;
}

function useUserContext(): UserContextValue {
  const value = useContext(UserContext);
  if (!value) throw new Error("useUser must be used inside UserProvider");
  return value;
}

export function useUser(): User {
  return useUserContext().user;
}

/** False when sign-in is turned off and everyone shares one workspace. */
export function useAuthRequired(): boolean {
  return useUserContext().authRequired;
}
