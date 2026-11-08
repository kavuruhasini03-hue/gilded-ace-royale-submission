import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import token from "./api/token.mjs";

const port = Number(process.env.PORT || 3000);
process.env.EMBED_ORIGIN = `http://localhost:${port}`;
const files = new Map([
  ["/", ["public/index.html", "text/html"]],
  ["/gold.json", ["public/gold.json", "application/json"]],
  ["/live", ["live.html", "text/html"]],
  ["/style.css", ["style.css", "text/css"]],
  ["/dashboard.mjs", ["dashboard.mjs", "text/javascript"]],
]);
createServer(async (req, res) => {
  if (req.url === "/api/token") return token(req, res);
  const entry = files.get(req.url);
  if (!entry || req.method !== "GET") return res.writeHead(404).end();
  const [path, type] = entry;
  try {
    const data = await readFile(new URL(path, import.meta.url));
    res.writeHead(200, { "Content-Type": `${type}; charset=utf-8` }).end(data);
  } catch {
    res.writeHead(500).end();
  }
}).listen(port, "127.0.0.1", () => console.log(`Local preview: http://localhost:${port}`));
