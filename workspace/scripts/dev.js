const { spawn, spawnSync } = require("node:child_process");

function runTypecheck(name, workspace) {
  const result = spawnSync(
    "npm",
    [
      "--workspace",
      workspace,
      "exec",
      "--",
      "tsc",
      "-p",
      "tsconfig.json",
      "--noEmit",
    ],
    { stdio: "inherit", shell: false },
  );

  if ((result.status ?? 1) !== 0) {
    process.exit(result.status ?? 1);
  }

  console.log(`[${name}] typecheck passed`);
}

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

runTypecheck("typecheck:server", "server");
runTypecheck("typecheck:client", "client");

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
