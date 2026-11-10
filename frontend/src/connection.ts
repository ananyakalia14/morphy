import { useEffect, useState } from "react";

type NetworkInfo = EventTarget & {
  saveData?: boolean;
  effectiveType?: string;
  downlink?: number;
};

export function shouldSaveData(info?: Pick<NetworkInfo, "saveData" | "effectiveType" | "downlink">) {
  return Boolean(info?.saveData ||
    (info?.effectiveType && info.effectiveType !== "4g") ||
    (info?.downlink && info.downlink > 0 && info.downlink < 1.5));
}

export function useConstrainedConnection() {
  const info = (navigator as Navigator & { connection?: NetworkInfo }).connection;
  const [constrained, setConstrained] = useState(() => shouldSaveData(info));
  useEffect(() => {
    const update = () => setConstrained(shouldSaveData(info));
    info?.addEventListener("change", update);
    return () => info?.removeEventListener("change", update);
  }, [info]);
  return constrained;
}
