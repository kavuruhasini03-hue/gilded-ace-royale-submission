const status = document.getElementById("status");
try {
  const response = await fetch("/api/token", { method: "POST", cache: "no-store" });
  const config = await response.json();
  if (!response.ok) throw new Error(config.error);
  const { DatabricksDashboard } = await import("https://cdn.jsdelivr.net/npm/@databricks/aibi-client@0.0.0-alpha.7/+esm");
  const { expiresIn, ...options } = config;
  const dashboard = new DatabricksDashboard({
    ...options, container: document.getElementById("dashboard"), colorScheme: "dark",
  });
  await dashboard.initialize();
  status.hidden = true;
} catch (error) {
  status.textContent = error.message || "The dashboard could not load.";
}
