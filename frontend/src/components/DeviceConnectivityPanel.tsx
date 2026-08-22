import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import type { UserRole } from "../lib/types";
import { api } from "../lib/api";
import type {
  ConfigurationSyncResult,
  Device,
  MqttCredentialSecret,
  MqttCredentialStatus,
} from "../lib/types";
import { ErrorNotice, StatusBadge, formatDate, formatRelative } from "./Ui";

export function DeviceConnectivityPanel({
  device,
  role,
}: {
  device: Device;
  role?: UserRole;
}) {
  const queryClient = useQueryClient();
  const [secret, setSecret] = useState<MqttCredentialSecret>();
  const [copied, setCopied] = useState(false);
  const [syncResult, setSyncResult] = useState<ConfigurationSyncResult>();
  const credentials = useQuery({
    queryKey: ["mqtt-credentials", device.id],
    queryFn: () =>
      api<MqttCredentialStatus>(
        `/devices/${device.id}/mqtt-credentials/status`,
      ),
    refetchInterval: 5000,
  });
  const refreshCredentials = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["mqtt-credentials", device.id],
    });
  };
  const provision = useMutation({
    mutationFn: () =>
      api<MqttCredentialSecret>(`/devices/${device.id}/mqtt-credentials`, {
        method: "POST",
      }),
    onSuccess: async (value) => {
      setSecret(value);
      setCopied(false);
      await refreshCredentials();
    },
  });
  const rotate = useMutation({
    mutationFn: () =>
      api<MqttCredentialSecret>(
        `/devices/${device.id}/mqtt-credentials/rotate`,
        { method: "POST" },
      ),
    onSuccess: async (value) => {
      setSecret(value);
      setCopied(false);
      await refreshCredentials();
    },
  });
  const revoke = useMutation({
    mutationFn: () =>
      api<MqttCredentialStatus>(
        `/devices/${device.id}/mqtt-credentials/revoke`,
        { method: "POST" },
      ),
    onSuccess: async () => {
      setSecret(undefined);
      await refreshCredentials();
    },
  });
  const sync = useMutation({
    mutationFn: () =>
      api<ConfigurationSyncResult>(`/devices/${device.id}/sync-configuration`, {
        method: "POST",
      }),
    onSuccess: async (value) => {
      setSyncResult(value);
      await queryClient.invalidateQueries({
        queryKey: ["device-sensors", device.id],
      });
      await queryClient.invalidateQueries({ queryKey: ["sensors"] });
      await queryClient.invalidateQueries({ queryKey: ["sensor"] });
    },
  });
  const mutationError =
    provision.error ?? rotate.error ?? revoke.error ?? sync.error;
  const copySecret = async () => {
    if (!secret) return;
    await navigator.clipboard.writeText(
      `SIMULATOR_MQTT_USERNAME=${secret.username}\nSIMULATOR_MQTT_PASSWORD=${secret.password}`,
    );
    setCopied(true);
  };
  return (
    <section className="panel mt-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold">Connectivity & MQTT</h2>
          <p className="mt-1 text-sm text-slate-400">
            Broker-authenticated Device identity and actual heartbeat state.
          </p>
        </div>
        <div className="text-right">
          <StatusBadge status={device.status} />
          <p
            className="mt-2 text-sm text-slate-300"
            title={formatDate(device.last_seen_at)}
          >
            {formatRelative(device.last_seen_at)}
          </p>
        </div>
      </div>
      {credentials.error ? (
        <div className="mt-5">
          <ErrorNotice error={credentials.error} />
        </div>
      ) : null}
      {mutationError ? (
        <div className="mt-5">
          <ErrorNotice error={mutationError} />
        </div>
      ) : null}
      <div className="mt-5 grid gap-4 rounded-xl border border-slate-800 bg-slate-950/50 p-4 sm:grid-cols-3">
        <div>
          <span className="meta">Credential status</span>
          <p className="mt-1 font-semibold">
            {credentials.isPending
              ? "Loading…"
              : credentials.data?.state.replace("_", " ")}
          </p>
        </div>
        <div>
          <span className="meta">MQTT username</span>
          <p className="mt-1 break-all font-mono text-sm">
            {credentials.data?.username ?? "—"}
          </p>
        </div>
        <div>
          <span className="meta">Last rotation</span>
          <p className="mt-1 text-sm">
            {formatDate(credentials.data?.rotated_at ?? null)}
          </p>
        </div>
      </div>
      <div className="mt-5 flex flex-wrap gap-3">
        {role === "ADMIN" && credentials.data?.state === "NOT_PROVISIONED" ? (
          <button
            className="button-primary"
            disabled={provision.isPending}
            onClick={() => provision.mutate()}
          >
            Provision Credentials
          </button>
        ) : null}
        {role === "ADMIN" && credentials.data?.provisioned ? (
          <button
            className="button-secondary"
            disabled={rotate.isPending}
            onClick={() => rotate.mutate()}
          >
            Rotate Credentials
          </button>
        ) : null}
        {role === "ADMIN" && credentials.data?.state === "ACTIVE" ? (
          <button
            className="button-secondary border-red-800 text-red-300"
            disabled={revoke.isPending}
            onClick={() => revoke.mutate()}
          >
            Revoke Credentials
          </button>
        ) : null}
        {role !== "VIEWER" ? (
          <button
            className="button-primary"
            disabled={sync.isPending}
            onClick={() => sync.mutate()}
          >
            {sync.isPending ? "Synchronizing…" : "Synchronize Configuration"}
          </button>
        ) : null}
      </div>
      {secret ? (
        <div
          role="alert"
          className="mt-5 rounded-xl border border-amber-500/40 bg-amber-500/10 p-5"
        >
          <h3 className="font-bold text-amber-200">New MQTT credentials</h3>
          <p className="mt-2 text-sm text-amber-100">
            This MQTT password is shown only once. Store it securely before
            closing this panel.
          </p>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="meta">Username</dt>
              <dd className="mt-1 break-all font-mono text-sm">
                {secret.username}
              </dd>
            </div>
            <div>
              <dt className="meta">Password</dt>
              <dd className="mt-1 break-all font-mono text-sm">
                {secret.password}
              </dd>
            </div>
          </dl>
          <div className="mt-4 flex gap-3">
            <button
              className="button-secondary"
              onClick={() => void copySecret()}
            >
              {copied ? "Copied" : "Copy simulator variables"}
            </button>
            <button
              className="button-secondary"
              onClick={() => setSecret(undefined)}
            >
              I stored it — close
            </button>
          </div>
        </div>
      ) : null}
      {syncResult ? (
        <p
          role="status"
          className="mt-5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-200"
        >
          Configuration snapshot published for {syncResult.sensor_count} Sensor
          {syncResult.sensor_count === 1 ? "" : "s"}. Awaiting Device
          acknowledgement.
        </p>
      ) : null}
    </section>
  );
}
