declare const process: {
  env: {
    PORT?: string;
    MAP_GENERATOR?: string;
    MAP_SEED?: string;
    MAP_FILE?: string;
  };
  cwd(): string;
};

declare const Buffer: {
  byteLength(input: string): number;
};

declare module 'node:http' {
  function http(...args: never[]): never;

  namespace http {
    interface IncomingMessage extends AsyncIterable<string | Uint8Array> {
      method?: string;
      url?: string;
      headers: Record<string, string | string[] | undefined>;
    }

    interface ServerResponse {
      setHeader(name: string, value: string | number): void;
      writeHead(statusCode: number, headers?: Record<string, string | number>): ServerResponse;
      end(chunk?: string | Uint8Array): void;
    }

    interface Server {
      listen(port: number, cb?: () => void): void;
    }

    function createServer(
      listener: (req: IncomingMessage, res: ServerResponse) => void | Promise<void>,
    ): Server;
  }

  export = http;
}

declare module 'node:url' {
  export class URL {
    constructor(input: string, base?: string | URL);
    pathname: string;
  }
}
