const { spawn } = require("node:child_process");

function start(name, args) {
  const child = spawn("npm", args, {
    stdio: ["inherit", "pipe", "pipe"],
    shell: false,
  });

  const prefix = `[${name}] `;
  child.stdout.on("data", (chunk) =>
    process.stdout.write(
      prefix + chunk.toString().replace(/\n/g, `\n${prefix}`),
    ),
  );
  child.stderr.on("data", (chunk) =>
    process.stderr.write(
      prefix + chunk.toString().replace(/\n/g, `\n${prefix}`),
    ),
  );
  return child;
}

const server = start("dev:server", ["--workspace", "server", "run", "dev"]);
const client = start("dev:client", ["--workspace", "client", "run", "dev"]);

const shutdown = () => {
  server.kill("SIGINT");
  client.kill("SIGINT");
};

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

server.on("exit", (code) => {
  if (code && code !== 0) {
    client.kill("SIGINT");
    process.exitCode = code;
  }
});

client.on("exit", (code) => {
  if (code && code !== 0) {
    server.kill("SIGINT");
    process.exitCode = code;
  }
});
