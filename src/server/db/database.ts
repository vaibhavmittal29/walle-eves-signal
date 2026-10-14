import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let globalDb: Database.Database | null = null;

export interface DatabaseOptions {
  dbPath?: string;
  inMemory?: boolean;
}

export function initDatabase(options: DatabaseOptions = {}): Database.Database {
  let dbFilePath: string;

  if (options.inMemory) {
    dbFilePath = ':memory:';
  } else if (options.dbPath) {
    dbFilePath = options.dbPath;
    const parentDir = path.dirname(dbFilePath);
    if (!fs.existsSync(parentDir)) {
      fs.mkdirSync(parentDir, { recursive: true });
    }
  } else {
    const dataDir = path.resolve(process.cwd(), 'data');
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
    const screenshotsDir = path.resolve(dataDir, 'screenshots');
    if (!fs.existsSync(screenshotsDir)) {
      fs.mkdirSync(screenshotsDir, { recursive: true });
    }
    dbFilePath = path.join(dataDir, 'changewatch.db');
  }

  const db = new Database(dbFilePath);

  // Performance & Integrity Pragmas
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
  db.pragma('busy_timeout = 5000');
  db.pragma('synchronous = NORMAL');

  // Load and execute schema
  const candidatePaths = [
    path.resolve(__dirname, 'schema.sql'),
    path.resolve(process.cwd(), 'src/server/db/schema.sql'),
    path.resolve(__dirname, '../src/server/db/schema.sql'),
    path.resolve(process.cwd(), 'dist/schema.sql'),
  ];
  const schemaPath = candidatePaths.find(p => fs.existsSync(p));
  if (!schemaPath) {
    throw new Error(`Cannot find schema.sql in candidate paths: ${candidatePaths.join(', ')}`);
  }
  const schemaSql = fs.readFileSync(schemaPath, 'utf8');
  db.exec(schemaSql);

  return db;
}

export function getDatabase(): Database.Database {
  if (!globalDb) {
    globalDb = initDatabase();
  }
  return globalDb;
}

export function closeDatabase(): void {
  if (globalDb) {
    globalDb.close();
    globalDb = null;
  }
}
