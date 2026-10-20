const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const { pipeline } = require("node:stream");
const { URL } = require("node:url");

const clientRoot = path.resolve(__dirname, "..");
const distDir = path.join(clientRoot, "dist");
const publicDir = path.join(clientRoot, "public");
const apiTarget = { hostname: "127.0.0.1", port: 3001 };

const mimeTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".svg", "image/svg+xml"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".gif", "image/gif"],
  [".webp", "image/webp"],
  [".map", "application/json; charset=utf-8"],
]);

function sendFile(res, filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const contentType = mimeTypes.get(ext) ?? "application/octet-stream";
  fs.stat(filePath, (err, stat) => {
    if (err || !stat.isFile()) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("Not found");
      return;
    }
    res.writeHead(200, {
      "Content-Type": contentType,
      "Content-Length": stat.size,
    });
    pipeline(fs.createReadStream(filePath), res, () => {});
  });
}

function proxyApi(req, res) {
  const upstream = http.request(
    {
      hostname: apiTarget.hostname,
      port: apiTarget.port,
      path: req.url,
      method: req.method,
      headers: req.headers,
    },
    (upstreamRes) => {
      res.writeHead(upstreamRes.statusCode ?? 500, upstreamRes.headers);
      upstreamRes.pipe(res);
    },
  );

  upstream.on("error", (error) => {
    res.writeHead(502, { "Content-Type": "text/plain; charset=utf-8" });
    res.end(`API proxy error: ${error.message}`);
  });

  req.pipe(upstream);
}

function resolveStatic(pathname) {
  const clean = pathname === "/" ? "/index.html" : pathname;
  const distCandidate = path.join(distDir, clean);
  if (fs.existsSync(distCandidate) && fs.statSync(distCandidate).isFile())
    return distCandidate;
  const publicCandidate = path.join(publicDir, clean);
  if (fs.existsSync(publicCandidate) && fs.statSync(publicCandidate).isFile())
    return publicCandidate;
  return null;
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url ?? "/", "http://localhost:8080");
  const pathname = decodeURIComponent(url.pathname);

  if (pathname.startsWith("/api/")) {
    proxyApi(req, res);
    return;
  }

  const filePath = resolveStatic(pathname);
  if (filePath) {
    sendFile(res, filePath);
    return;
  }

  res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
  res.end("Not found");
});

server.listen(8080, () => {
  console.log("Picaro client on http://localhost:8080");
});
