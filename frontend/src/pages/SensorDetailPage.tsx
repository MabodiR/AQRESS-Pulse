import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import {
  ErrorNotice,
  PageHeader,
  StatusBadge,
  formatDate,
} from "../components/Ui";
import { api } from "../lib/api";
import type { Sensor, SensorChannel, SensorConfiguration } from "../lib/types";

function ChannelEditor({
  sensorId,
  channel,
  onSaved,
}: {
  sensorId: string;
  channel: SensorChannel;
  onSaved: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState({
    name: channel.name,
    unit: channel.unit ?? "",
    enabled: channel.enabled,
  });
  const mutation = useMutation({
    mutationFn: () =>
      api<SensorChannel>(`/sensors/${sensorId}/channels/${channel.id}`, {
        method: "PUT",
        body: JSON.stringify({ ...values, unit: values.unit || null }),
      }),
    onSuccess: async () => {
      setEditing(false);
      await onSaved();
    },
  });
  if (!editing)
    return (
      <tr>
        <td>{channel.name}</td>
        <td>{channel.key}</td>
        <td>{channel.unit || "—"}</td>
        <td>
          <StatusBadge active={channel.enabled} />
        </td>
        <td>
          <button className="button-secondary" onClick={() => setEditing(true)}>
            Edit
          </button>
        </td>
      </tr>
    );
  return (
    <tr>
      <td>
        <input
          aria-label={`${channel.key} channel name`}
          className="input min-w-44"
          value={values.name}
          onChange={(event) =>
            setValues((value) => ({ ...value, name: event.target.value }))
          }
        />
      </td>
      <td>{channel.key}</td>
      <td>
        <input
          aria-label={`${channel.key} unit`}
          className="input w-28"
          value={values.unit}
          onChange={(event) =>
            setValues((value) => ({ ...value, unit: event.target.value }))
          }
        />
      </td>
      <td>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={values.enabled}
            onChange={(event) =>
              setValues((value) => ({
                ...value,
                enabled: event.target.checked,
              }))
            }
          />{" "}
          Enabled
        </label>
      </td>
      <td>
        <div className="flex gap-2">
          <button
            className="button-primary"
            disabled={!values.name.trim() || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            Save
          </button>
          <button
            className="button-secondary"
            onClick={() => setEditing(false)}
          >
            Cancel
          </button>
        </div>
        {mutation.error ? (
          <span className="field-error">{mutation.error.message}</span>
        ) : null}
      </td>
    </tr>
  );
}

export function SensorDetailPage() {
  const { sensorId } = useParams();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const sensor = useQuery({
    queryKey: ["sensor", sensorId],
    queryFn: () => api<Sensor>(`/sensors/${sensorId}`),
  });
  const history = useQuery({
    queryKey: ["sensor-configurations", sensorId],
    queryFn: () =>
      api<SensorConfiguration[]>(`/sensors/${sensorId}/configurations`),
  });
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["sensor", sensorId] });
    await queryClient.invalidateQueries({ queryKey: ["sensors"] });
  };
  const status = useMutation({
    mutationFn: (enabled: boolean) =>
      api<Sensor>(`/sensors/${sensorId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ enabled }),
      }),
    onSuccess: refresh,
  });
  if (sensor.isPending) return <div className="panel">Loading Sensor…</div>;
  if (sensor.error || !sensor.data) return <ErrorNotice error={sensor.error} />;
  const item = sensor.data;
  const canWrite = user?.role !== "VIEWER";
  const details = [
    ["Device", item.device.name],
    ["Site", item.device.site.name],
    ["Sensor Type", item.sensor_type.code],
    ["Interface", item.sensor_type.interface_type],
    ["Enabled", item.enabled ? "Yes" : "No"],
    ["Created", formatDate(item.created_at)],
    ["Updated", formatDate(item.updated_at)],
  ];
  return (
    <>
      <PageHeader
        title={item.name}
        description={`${item.sensor_uid} · ${item.sensor_type.name}`}
        action={
          canWrite ? (
            <div className="flex gap-3">
              <Link
                className="button-secondary"
                to={`/sensors/${item.id}/edit`}
              >
                Edit Sensor
              </Link>
              <Link
                className="button-primary"
                to={`/sensors/${item.id}/configuration`}
              >
                Edit Configuration
              </Link>
            </div>
          ) : undefined
        }
      />
      <div className="mb-7 flex flex-wrap items-center gap-3">
        <StatusBadge status={item.status} />
        <StatusBadge status={item.current_configuration.status} />
        {item.current_configuration.status === "PENDING" ? (
          <span className="text-sm text-amber-300">
            Pending device synchronization — MQTT delivery begins in a later
            phase.
          </span>
        ) : null}
        {canWrite ? (
          <button
            className="button-secondary"
            disabled={status.isPending}
            onClick={() => status.mutate(!item.enabled)}
          >
            {item.enabled ? "Disable Sensor" : "Enable Sensor"}
          </button>
        ) : null}
      </div>
      <dl className="panel grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {details.map(([label, value]) => (
          <div key={label}>
            <dt className="meta">{label}</dt>
            <dd className="mt-1">
              {label === "Device" ? (
                <Link
                  className="font-semibold text-cyan-300"
                  to={`/devices/${item.device.id}`}
                >
                  {value}
                </Link>
              ) : label === "Sensor Type" ? (
                <Link
                  className="font-semibold text-cyan-300"
                  to={`/sensor-types/${item.sensor_type.id}`}
                >
                  {value}
                </Link>
              ) : (
                value
              )}
            </dd>
          </div>
        ))}
      </dl>
      <section
        className="panel mt-7 overflow-x-auto"
        tabIndex={0}
        aria-label="Measurement Channels table"
      >
        <h2 className="text-xl font-bold">Measurement Channels</h2>
        <p className="mt-1 text-sm text-slate-400">
          Channel identity is fixed; display name, unit, and enabled state are
          editable.
        </p>
        <table className="mt-4">
          <thead>
            <tr>
              <th>Name</th>
              <th>Key</th>
              <th>Unit</th>
              <th>Status</th>
              {canWrite ? <th>Action</th> : null}
            </tr>
          </thead>
          <tbody>
            {item.channels.map((channel) =>
              canWrite ? (
                <ChannelEditor
                  key={channel.id}
                  sensorId={item.id}
                  channel={channel}
                  onSaved={refresh}
                />
              ) : (
                <tr key={channel.id}>
                  <td>{channel.name}</td>
                  <td>{channel.key}</td>
                  <td>{channel.unit || "—"}</td>
                  <td>
                    <StatusBadge active={channel.enabled} />
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </section>
      <section className="panel mt-7">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold">Current Desired Configuration</h2>
            <p className="mt-1 text-sm text-slate-400">
              Version {item.current_configuration.config_version} · created{" "}
              {formatDate(item.current_configuration.created_at)}
            </p>
          </div>
          <StatusBadge status={item.current_configuration.status} />
        </div>
        <pre className="mt-5 overflow-auto rounded-xl bg-slate-950 p-4 text-sm text-slate-300">
          {JSON.stringify(item.current_configuration.configuration, null, 2)}
        </pre>
      </section>
      <section
        className="panel mt-7 overflow-x-auto"
        tabIndex={0}
        aria-label="Configuration History table"
      >
        <h2 className="text-xl font-bold">Configuration History</h2>
        {history.error ? (
          <div className="mt-4">
            <ErrorNotice error={history.error} />
          </div>
        ) : null}
        {history.isPending ? (
          <p className="mt-4 text-slate-400">Loading history…</p>
        ) : (
          <table className="mt-4">
            <thead>
              <tr>
                <th>Version</th>
                <th>Status</th>
                <th>Created</th>
                <th>Published</th>
                <th>Applied</th>
                <th>Current</th>
              </tr>
            </thead>
            <tbody>
              {history.data?.map((configuration) => (
                <tr key={configuration.id}>
                  <td>v{configuration.config_version}</td>
                  <td>
                    <StatusBadge status={configuration.status} />
                  </td>
                  <td>{formatDate(configuration.created_at)}</td>
                  <td>{formatDate(configuration.published_at)}</td>
                  <td>{formatDate(configuration.applied_at)}</td>
                  <td>{configuration.is_current ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}
