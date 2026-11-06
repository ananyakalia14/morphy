import { useState } from "react";
export function useAction() {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function run(f: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await f();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, run };
}
