import { useEffect, useState } from "react";
import { Loading } from "../components/ui";
import { api } from "../lib/api";

/** Private files need the auth cookie, so they are fetched with credentials and shown via an object URL. */
export function PrivateImage({ path }: { path: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let url: string | null = null;
    api.imageUrl(path).then((u) => { url = u; setSrc(u); }).catch(() => setFailed(true));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [path]);
  if (failed) return <p className="text-sm text-slate-500">Photo unavailable.</p>;
  return src ? <img src={src} alt="Visit" className="max-h-64 rounded-md border" /> : <Loading />;
}
