import { createContext, useContext } from "react";
import type { Bootstrap } from "./api";

export type AppContextValue = {
  bootstrap: Bootstrap;
  refresh: () => Promise<void>;
  notify: (message: string) => void;
};
export const AppContext = createContext<AppContextValue | null>(null);
export function useApp() {
  const value = useContext(AppContext);
  if (!value) throw new Error("Portal no inicializado");
  return value;
}
