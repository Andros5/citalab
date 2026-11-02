let locks = 0;
let restore: (() => void) | undefined;

/** Each modal owns one release function; nested modals cannot unlock each other. */
export function acquireScrollLock() {
  if (locks === 0) {
    const targets = [document.documentElement, document.body];
    const styles = targets.map((target) => ({
      value: target.style.getPropertyValue("overflow"),
      priority: target.style.getPropertyPriority("overflow"),
    }));
    targets.forEach((target) => target.style.setProperty("overflow", "hidden"));
    restore = () =>
      targets.forEach((target, i) => {
        if (styles[i].value)
          target.style.setProperty(
            "overflow",
            styles[i].value,
            styles[i].priority,
          );
        else target.style.removeProperty("overflow");
      });
  }
  locks += 1;
  let released = false;
  return () => {
    if (released) return;
    released = true;
    locks -= 1;
    if (locks === 0) {
      restore?.();
      restore = undefined;
    }
  };
}
