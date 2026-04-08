import { createSignal } from "solid-js";
import { apiGet, apiPost } from "./api";
import type { UserOut } from "../types/api";

const [currentUser, setCurrentUser] = createSignal<UserOut | null>(null);
export { currentUser };

export async function fetchCurrentUser(): Promise<UserOut | null> {
  try {
    const user = await apiGet<UserOut>("/api/me");
    setCurrentUser(user);
    return user;
  } catch {
    setCurrentUser(null);
    return null;
  }
}

export async function login(username: string, password: string): Promise<void> {
  await apiPost("/api/auth/login", { username, password });
  await fetchCurrentUser();
}

export async function logout(): Promise<void> {
  await apiPost("/api/auth/logout");
  setCurrentUser(null);
}
