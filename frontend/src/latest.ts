/** Tracks the newest request so older responses can be ignored. */
export function createLatest() {
  let current = 0;
  return {
    next() {
      const token = ++current;
      return () => token === current;
    },
    cancel() {
      current++;
    },
  };
}
