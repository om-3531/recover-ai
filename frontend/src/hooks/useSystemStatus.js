import { useEffect, useState } from "react";
import { getBackendHealth } from "../services/api";

/**
 * Tracks whether the backend is reachable. Used by the dashboard's
 * "System Status" card. Fails gracefully to an "offline" state instead
 * of throwing, since the dashboard should always render.
 */
export function useSystemStatus() {
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    let isMounted = true;

    getBackendHealth()
      .then(() => {
        if (isMounted) setStatus("online");
      })
      .catch(() => {
        if (isMounted) setStatus("offline");
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return status;
}
