import SkeletonBlock from "./SkeletonBlock";

export default function StatusGate({
  status,
  skeleton,
  empty,
  error,
  children,
}) {
  if (status === "loading") return skeleton ?? <SkeletonBlock />;
  if (status === "error") return error;
  if (status === "empty") return empty;
  return children;
}
