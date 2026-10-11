export interface Settings {
  schemaVersion: number;
  namespace: string;
  hfEndpoint: string;
  offline: boolean;
  enableImageModels: boolean;
  fastSynch: boolean;
  startOnLogin: boolean;
  defaultModelsDirectory: string;
  additionalModelsDirectories: string[];
  readOnlyModelsDirectories: string[];
  customEnvironment: Record<string, string>;
  onboardingCompleted: boolean;
}
export interface SavedSettings {
  settings: Settings;
  hfTokenPresent: boolean;
}
export type BackendStatus =
  | "Stopped"
  | "Starting"
  | "Running"
  | "Stopping"
  | "Failed"
  | "External";
export interface Snapshot {
  status: BackendStatus;
  detail: string;
  owned: boolean;
  nodeId: string | null;
  version: string;
  runtimePath: string;
  sourceCommit: string | null;
  sourceModified: boolean;
  mlxVersion: string | null;
  dataPath: string;
  logPath: string;
  update: { version: string; body: string } | null;
  updaterConfigured: boolean;
}
export type JsonObject = Record<string, unknown>;
export interface Node {
  id: string;
  name: string;
  chip: string;
  os: string;
  total: number;
  available: number;
  gpu: number | null;
  cpu: number | null;
  temperature: number | null;
  power: number | null;
  backends: string[];
}
export interface Instance {
  id: string;
  model: string;
  kind: string;
  nodes: string[];
  runners: string[];
  status: string;
  tasks: Task[];
}
export interface Task {
  id: string;
  kind: string;
  status: string;
  prompt: string;
  error: string;
}
export interface Download {
  node: string;
  model: string;
  kind: string;
  downloaded: number;
  total: number;
  speed: number;
  eta: number;
  error: string;
  readOnly: boolean;
  shard: unknown;
}
export interface Cluster {
  nodes: Node[];
  edges: { source: string; target: string; rdma: boolean }[];
  instances: Instance[];
  downloads: Download[];
  tasks: Task[];
}
